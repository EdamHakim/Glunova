from rest_framework import status, serializers
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.core.files.storage import default_storage
from django.http import FileResponse

from .models import MedicalDocument
from .serializers import MedicalDocumentSerializer, MedicalDocumentListSerializer
from .services.pipeline import process_document_upload
from .services.storage import create_download_payload


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        u = request.user
        return Response(
            {
                "id": str(u.pk),
                "username": u.username,
                "email": u.email,
                "role": getattr(u, "role", "patient"),
                "full_name": u.get_full_name() or u.username,
            }
        )


class DocumentListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        patient_id = request.query_params.get("patient_id")
        if not patient_id:
            return Response({"detail": "patient_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check permissions: doctor/caregiver can see anything, patient only their own
        if request.user.role == 'patient' and str(request.user.id) != str(patient_id):
            return Response({"detail": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)

        docs = MedicalDocument.objects.filter(patient_id=patient_id).order_by("-created_at")
        serializer = MedicalDocumentListSerializer(docs, many=True)
        return Response({"items": serializer.data, "total": docs.count()})

    def post(self, request):
        patient_id = request.data.get("patient_id")
        file = request.FILES.get("file")

        if not patient_id or not file:
            return Response(
                {"detail": "patient_id and file are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            mime_type = file.content_type
            original_filename = file.name
            file_bytes = file.read()
            
            # Prepare storage path
            from .services.pipeline import safe_filename
            s_name = safe_filename(original_filename)
            storage_path = f"patient_{patient_id}/{s_name}"

            # Create the record in PENDING state
            doc = MedicalDocument.objects.create(
                patient_id=patient_id,
                original_filename=original_filename,
                mime_type=mime_type,
                storage_path=storage_path,
                processing_status=MedicalDocument.ProcessingStatus.PENDING,
            )

            # Run the pipeline (storage, OCR, validation)
            process_document_upload(doc, file_bytes, mime_type)
            
            serializer = MedicalDocumentSerializer(doc)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Upload failed: {str(e)}", exc_info=True)
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DocumentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        doc = get_object_or_404(MedicalDocument, pk=pk)
        # Permission check
        if request.user.role == 'patient' and str(request.user.id) != str(doc.patient_id):
             return Response({"detail": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
             
        serializer = MedicalDocumentSerializer(doc)
        return Response(serializer.data)


class DocumentDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        doc = get_object_or_404(MedicalDocument, pk=pk)
        # Permission check
        if request.user.role == 'patient' and str(request.user.id) != str(doc.patient_id):
            return Response({"detail": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)

        try:
            payload = create_download_payload(doc)
            if payload["type"] == "url":
                return Response({"url": payload["url"]})
            else:
                return FileResponse(
                    payload["content"],
                    as_attachment=True,
                    filename=payload["filename"],
                )
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DebugGeminiView(APIView):
    permission_classes = [] 

    def get(self, request):
        from .services.gemini_ocr import perform_ocr
        import os
        from PIL import Image
        import io

        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
             return Response({"status": "error", "message": "No API key found in env"})

        try:
            dummy_img = Image.new('RGB', (100, 100), color = 'red')
            img_byte_arr = io.BytesIO()
            dummy_img.save(img_byte_arr, format='JPEG')
            
            result = perform_ocr(img_byte_arr.getvalue(), "image/jpeg")
            return Response({
                "status": "success",
                "message": "Gemini API reached",
                "ocr_sample": result[:100] if result else "No text returned"
            })
        except Exception as e:
            import traceback
            return Response({
                "status": "error",
                "message": str(e),
                "trace": traceback.format_exc()
            }, status=500)
