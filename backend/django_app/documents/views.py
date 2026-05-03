from rest_framework import status, serializers
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.http import FileResponse, HttpResponseRedirect
from uuid import uuid4

from .models import MedicalDocument
from .serializers import MedicalDocumentSerializer, MedicalDocumentListSerializer
from .access import can_access_patient_documents, parse_patient_pk, patient_exists
from .services.pipeline import process_document_upload
from .services.storage import create_download_payload


class MeView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        u = request.user
        data = {
            "id": str(u.pk),
            "username": u.username,
            "email": u.email,
            "role": getattr(u, "role", "patient"),
            "full_name": u.get_full_name() or u.username,
        }

        if getattr(u, "role", None) == "patient":
            p = getattr(u, "patient_profile", None)
            if p:
                data.update({
                    "age":                 p.age,
                    "date_of_birth":       p.date_of_birth.isoformat() if p.date_of_birth else None,
                    "gender":              p.gender,
                    "weight_kg":           float(p.weight_kg) if p.weight_kg else None,
                    "height_cm":           float(p.height_cm) if p.height_cm else None,
                    "hypertension":        p.hypertension,
                    "heart_disease":       p.heart_disease,
                    "smoking_status":      p.smoking_status,
                    "hba1c_level":         float(p.hba1c_level) if p.hba1c_level else None,
                    "blood_glucose_level": p.blood_glucose_level,
                    "diabetes_type":       p.diabetes_type,
                    "allergies":           p.allergies,
                    "last_glucose":        f"{p.blood_glucose_level} mg/dL" if p.blood_glucose_level else None,
                    "carb_limit_per_meal_g": 60,
                })

        profile_picture_url = None
        if u.profile_picture:
            profile_picture_url = request.build_absolute_uri(u.profile_picture.url)
        data["profile_picture"] = profile_picture_url
        return Response(data)

    def patch(self, request):
        from django.core.exceptions import ValidationError as DjangoValidationError
        from django.db import IntegrityError
        from users.models import PatientProfile

        u = request.user
        data = request.data

        # Handle profile picture upload
        if "profile_picture" in request.FILES:
            if u.profile_picture:
                u.profile_picture.delete(save=False)
            u.profile_picture = request.FILES["profile_picture"]
            u.save(update_fields=["profile_picture"])

        # User-table fields
        user_updatable = ["first_name", "last_name", "email"]
        user_changes: list[str] = []
        for field in user_updatable:
            if field not in data:
                continue
            val = data[field]
            if val == "" or val is None:
                continue
            setattr(u, field, val)
            user_changes.append(field)
        if user_changes:
            try:
                u.save(update_fields=user_changes)
            except (DjangoValidationError, IntegrityError, ValueError, TypeError) as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        # Patient profile fields
        if getattr(u, "role", None) == "patient":
            profile_updatable = [
                "date_of_birth", "gender", "height_cm", "weight_kg",
                "hypertension", "heart_disease", "smoking_status",
                "hba1c_level", "blood_glucose_level", "diabetes_type", "allergies",
            ]
            profile_nullable = {
                "date_of_birth", "gender", "height_cm", "weight_kg",
                "hypertension", "heart_disease", "smoking_status",
                "hba1c_level", "blood_glucose_level",
            }
            profile, _ = PatientProfile.objects.get_or_create(user=u)
            profile_changes: list[str] = []
            for field in profile_updatable:
                if field not in data:
                    continue
                val = data[field]
                if field in profile_nullable:
                    setattr(profile, field, None if (val == "" or val is None) else val)
                else:
                    if val == "" or val is None:
                        continue
                    setattr(profile, field, val)
                profile_changes.append(field)
            if profile_changes:
                try:
                    profile.save(update_fields=profile_changes)
                except (DjangoValidationError, IntegrityError, ValueError, TypeError) as exc:
                    return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return self.get(request)


class DocumentListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        raw_patient_id = request.query_params.get("patient_id")
        if not raw_patient_id:
            return Response({"detail": "patient_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        patient_id = parse_patient_pk(raw_patient_id)
        if patient_id is None:
            return Response({"detail": "patient_id must be a positive integer"}, status=status.HTTP_400_BAD_REQUEST)
        if not patient_exists(patient_id):
            return Response({"detail": "Patient not found"}, status=status.HTTP_404_NOT_FOUND)
        if not can_access_patient_documents(request.user, patient_id):
            return Response({"detail": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)

        docs = MedicalDocument.objects.filter(patient_id=patient_id).order_by("-created_at")
        serializer = MedicalDocumentListSerializer(docs, many=True)
        return Response({"items": serializer.data, "total": docs.count()})

    def post(self, request):
        raw_patient_id = request.data.get("patient_id")
        file = request.FILES.get("file")

        if not raw_patient_id or not file:
            return Response(
                {"detail": "patient_id and file are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        patient_id = parse_patient_pk(raw_patient_id)
        if patient_id is None:
            return Response({"detail": "patient_id must be a positive integer"}, status=status.HTTP_400_BAD_REQUEST)
        if not patient_exists(patient_id):
            return Response({"detail": "Patient not found"}, status=status.HTTP_404_NOT_FOUND)
        if not can_access_patient_documents(request.user, patient_id):
            return Response({"detail": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)

        try:
            mime_type = file.content_type
            original_filename = file.name
            file_bytes = file.read()
            
            # Prepare storage path
            from .services.pipeline import safe_filename
            s_name = safe_filename(original_filename)
            # Use a unique object key to avoid storage collisions on same filename.
            storage_path = f"patient_{patient_id}/{uuid4().hex}_{s_name}"

            # Create the record in PENDING state
            doc = MedicalDocument.objects.create(
                patient_id=patient_id,
                uploaded_by=request.user,
                original_filename=original_filename,
                mime_type=mime_type,
                storage_path=storage_path,
                processing_status=MedicalDocument.ProcessingStatus.PENDING,
            )

            # Run the pipeline (storage, OCR, validation)
            process_document_upload(doc, file_bytes, mime_type)
            
            serializer = MedicalDocumentSerializer(doc)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except FileExistsError as e:
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Upload failed: {str(e)}", exc_info=True)
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DocumentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        doc = get_object_or_404(MedicalDocument, pk=pk)
        if not can_access_patient_documents(request.user, doc.patient_id):
            return Response({"detail": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
             
        serializer = MedicalDocumentSerializer(doc)
        return Response(serializer.data)


class DocumentDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        doc = get_object_or_404(MedicalDocument, pk=pk)
        if not can_access_patient_documents(request.user, doc.patient_id):
            return Response({"detail": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)

        try:
            payload = create_download_payload(doc)
            if payload["type"] == "url":
                return HttpResponseRedirect(payload["url"])
            else:
                return FileResponse(
                    payload["content"],
                    as_attachment=True,
                    filename=payload["filename"],
                )
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DocumentPreviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        doc = get_object_or_404(MedicalDocument, pk=pk)
        if not can_access_patient_documents(request.user, doc.patient_id):
            return Response({"detail": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)

        try:
            payload = create_download_payload(doc)
            if payload["type"] == "url":
                return HttpResponseRedirect(payload["url"])
            return FileResponse(
                payload["content"],
                as_attachment=False,
                filename=payload["filename"],
                content_type=doc.mime_type,
            )
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
