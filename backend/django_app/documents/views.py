from __future__ import annotations

import uuid

from django.core.files.storage import default_storage
from django.http import FileResponse
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .access import can_access_patient_documents, patient_exists
from .models import MedicalDocument
from .serializers import MedicalDocumentSerializer
from .services.pipeline import process_document_upload, safe_filename
from .services.storage import create_download_payload


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        u = request.user
        return Response(
            {
                "id": str(u.pk),
                "role": getattr(u, "role", "patient"),
                "full_name": u.get_full_name() or u.username,
            }
        )


class DocumentListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        raw_pid = request.query_params.get("patient_id")
        if not raw_pid:
            return Response({"detail": "patient_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            patient_pk = int(raw_pid)
        except (TypeError, ValueError):
            return Response({"detail": "Invalid patient_id"}, status=status.HTTP_400_BAD_REQUEST)

        if not patient_exists(patient_pk):
            return Response({"detail": "Patient not found"}, status=status.HTTP_404_NOT_FOUND)
        if not can_access_patient_documents(request.user, patient_pk):
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        try:
            page = max(1, int(request.query_params.get("page", 1)))
            page_size = min(100, max(1, int(request.query_params.get("page_size", 20))))
        except (TypeError, ValueError):
            return Response({"detail": "Invalid pagination"}, status=status.HTTP_400_BAD_REQUEST)

        qs = MedicalDocument.objects.filter(patient_id=patient_pk)
        total = qs.count()
        start = (page - 1) * page_size
        items = qs[start : start + page_size]
        ser = MedicalDocumentSerializer(items, many=True, context={"request": request})
        return Response({"items": ser.data, "total": total})

    def post(self, request):
        raw_pid = request.data.get("patient_id")
        if raw_pid is None:
            return Response({"detail": "patient_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            patient_pk = int(raw_pid)
        except (TypeError, ValueError):
            return Response({"detail": "Invalid patient_id"}, status=status.HTTP_400_BAD_REQUEST)

        if not patient_exists(patient_pk):
            return Response({"detail": "Patient not found"}, status=status.HTTP_404_NOT_FOUND)
        if not can_access_patient_documents(request.user, patient_pk):
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        upload = request.FILES.get("file")
        if not upload:
            return Response({"detail": "file is required"}, status=status.HTTP_400_BAD_REQUEST)

        mime = (upload.content_type or "application/octet-stream").split(";")[0].strip()
        doc_id = uuid.uuid4()
        safe = safe_filename(upload.name)
        storage_path = f"{patient_pk}/{doc_id}/{safe}"

        doc = MedicalDocument.objects.create(
            id=doc_id,
            patient_id=patient_pk,
            uploaded_by=request.user,
            original_filename=upload.name[:512],
            mime_type=mime[:128],
            storage_path=storage_path,
            processing_status=MedicalDocument.ProcessingStatus.PENDING,
        )

        data = upload.read()
        try:
            process_document_upload(doc, data, mime)
        except ValueError as exc:
            doc.processing_status = MedicalDocument.ProcessingStatus.FAILED
            doc.error_message = str(exc)[:2000]
            doc.save(
                update_fields=["processing_status", "error_message", "updated_at"],
            )
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            doc.processing_status = MedicalDocument.ProcessingStatus.FAILED
            doc.error_message = str(exc)[:2000]
            doc.save(
                update_fields=["processing_status", "error_message", "updated_at"],
            )
            return Response(
                {"detail": "Processing failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        doc.refresh_from_db()
        ser = MedicalDocumentSerializer(doc, context={"request": request})
        return Response(ser.data, status=status.HTTP_201_CREATED)


class DocumentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            doc_uuid = uuid.UUID(str(pk))
        except (ValueError, TypeError):
            return Response({"detail": "Invalid id"}, status=status.HTTP_400_BAD_REQUEST)

        doc = MedicalDocument.objects.filter(pk=doc_uuid).first()
        if not doc:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        if not can_access_patient_documents(request.user, doc.patient_id):
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        ser = MedicalDocumentSerializer(doc, context={"request": request})
        return Response(ser.data)


class DocumentDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            doc_uuid = uuid.UUID(str(pk))
        except (ValueError, TypeError):
            return Response({"detail": "Invalid id"}, status=status.HTTP_400_BAD_REQUEST)

        doc = MedicalDocument.objects.filter(pk=doc_uuid).first()
        if not doc:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        if not can_access_patient_documents(request.user, doc.patient_id):
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        try:
            kind, value = create_download_payload(doc.storage_path)
        except FileNotFoundError:
            return Response({"detail": "File not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception:
            return Response({"detail": "Download unavailable"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        if kind == "redirect":
            # JSON so the SPA can call with Authorization; browser redirects cannot attach Bearer.
            return Response({"url": value, "expires_in_seconds": 60})
        return FileResponse(
            default_storage.open(value, "rb"),
            as_attachment=True,
            filename=doc.original_filename,
        )

from django.conf import settings
import urllib.request
import json
class DebugGeminiView(APIView):
    permission_classes = []
    def get(self, request):
        api_key = getattr(settings, "GEMINI_API_KEY", "").strip()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
        data = json.dumps({"contents": [{"parts": [{"text": "Hello"}]}]}).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as response:
                return Response(json.loads(response.read().decode()))
        except urllib.error.HTTPError as e:
            return Response({"error_code": e.code, "error_body": json.loads(e.read().decode())})


