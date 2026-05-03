import logging
import os

import httpx
from django.contrib.auth import get_user_model
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from users.models import CaregiverProfile, DoctorProfile, PatientProfile

logger = logging.getLogger(__name__)
User = get_user_model()

_PATIENT_PROFILE_FIELDS = [
    "date_of_birth", "gender", "height_cm", "weight_kg",
    "hypertension", "heart_disease", "smoking_status",
    "hba1c_level", "blood_glucose_level", "diabetes_type", "allergies",
]
_DOCTOR_PROFILE_FIELDS    = ["specialization", "license_number", "hospital_affiliation"]
_CAREGIVER_PROFILE_FIELDS = ["relationship", "is_professional"]


def _trigger_fusion_refresh(patient_id: int) -> None:
    """Best-effort call to FastAPI to refresh the patient's tier.

    Failure is non-blocking: signup must succeed even if FastAPI is down or the
    patient skipped required health fields (HbA1c/glucose) — the route returns
    PATIENT_INCOMPLETE which we just log.
    """
    base = os.environ.get("FASTAPI_INTERNAL_URL", "http://127.0.0.1:8001")
    url = f"{base.rstrip('/')}/monitoring/internal/refresh-tier/{patient_id}"
    try:
        httpx.post(url, timeout=20.0)
    except Exception as exc:
        logger.warning("Fusion refresh ping failed for patient %s: %s", patient_id, exc)


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ("username", "email", "password", "first_name", "last_name", "role")

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class RegisterView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        role = user.role
        if role == "patient":
            profile_data = {k: request.data[k] for k in _PATIENT_PROFILE_FIELDS if k in request.data}
            PatientProfile.objects.create(user=user, **profile_data)
            _trigger_fusion_refresh(int(user.id))
        elif role == "doctor":
            profile_data = {k: request.data[k] for k in _DOCTOR_PROFILE_FIELDS if k in request.data}
            DoctorProfile.objects.create(user=user, **profile_data)
        elif role == "caregiver":
            profile_data = {k: request.data[k] for k in _CAREGIVER_PROFILE_FIELDS if k in request.data}
            CaregiverProfile.objects.create(user=user, **profile_data)

        return Response(
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
            },
            status=status.HTTP_201_CREATED,
        )


class GlunovaTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["username"] = user.username
        return token


from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken

class GlunovaTokenObtainPairView(TokenObtainPairView):
    serializer_class = GlunovaTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            access_token = response.data.get("access")
            refresh_token = response.data.get("refresh")
            
            # Use configurations from settings.SIMPLE_JWT
            jwt_conf = settings.SIMPLE_JWT
            
            response.set_cookie(
                key=jwt_conf.get("AUTH_COOKIE", "access_token"),
                value=access_token,
                httponly=jwt_conf.get("AUTH_COOKIE_HTTP_ONLY", True),
                path=jwt_conf.get("AUTH_COOKIE_PATH", "/"),
                samesite=jwt_conf.get("AUTH_COOKIE_SAMESITE", "Lax"),
                secure=jwt_conf.get("AUTH_COOKIE_SECURE", False), # False locally
            )
            response.set_cookie(
                key=jwt_conf.get("REFRESH_COOKIE", "refresh_token"),
                value=refresh_token,
                httponly=jwt_conf.get("REFRESH_COOKIE_HTTP_ONLY", True),
                path=jwt_conf.get("REFRESH_COOKIE_PATH", "/"),
                samesite=jwt_conf.get("REFRESH_COOKIE_SAMESITE", "Lax"),
                secure=jwt_conf.get("REFRESH_COOKIE_SECURE", False),
            )
            # Remove tokens from response body for extra security (optional)
            # response.data.pop("access", None)
            # response.data.pop("refresh", None)
        return response

from rest_framework_simplejwt.views import TokenRefreshView

class GlunovaTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        # If the 'refresh' token is not in the request body, try to get it from the cookie
        refresh_cookie_name = settings.SIMPLE_JWT.get("REFRESH_COOKIE", "refresh_token")
        if "refresh" not in request.data and refresh_cookie_name in request.COOKIES:
            # We can't easily mutate request.data as it's a QueryDict, 
            # so we prepare a modified data dictionary for the serializer.
            refresh_token = request.COOKIES.get(refresh_cookie_name)
            serializer = self.get_serializer(data={"refresh": refresh_token})
            
            try:
                serializer.is_valid(raise_exception=True)
            except Exception as e:
                return Response({"detail": str(e)}, status=status.HTTP_401_UNAUTHORIZED)
            
            response = Response(serializer.validated_data, status=status.HTTP_200_OK)
        else:
            response = super().post(request, *args, **kwargs)

        if response.status_code == 200:
            access_token = response.data.get("access")
            jwt_conf = settings.SIMPLE_JWT
            
            response.set_cookie(
                key=jwt_conf.get("AUTH_COOKIE", "access_token"),
                value=access_token,
                httponly=jwt_conf.get("AUTH_COOKIE_HTTP_ONLY", True),
                path=jwt_conf.get("AUTH_COOKIE_PATH", "/"),
                samesite=jwt_conf.get("AUTH_COOKIE_SAMESITE", "Lax"),
                secure=jwt_conf.get("AUTH_COOKIE_SECURE", False),
            )
            # If a new refresh token was returned (optional rotation), set it too
            new_refresh = response.data.get("refresh")
            if new_refresh:
                response.set_cookie(
                    key=jwt_conf.get("REFRESH_COOKIE", "refresh_token"),
                    value=new_refresh,
                    httponly=jwt_conf.get("REFRESH_COOKIE_HTTP_ONLY", True),
                    path=jwt_conf.get("REFRESH_COOKIE_PATH", "/"),
                    samesite=jwt_conf.get("REFRESH_COOKIE_SAMESITE", "Lax"),
                    secure=jwt_conf.get("REFRESH_COOKIE_SECURE", False),
                )
        return response

class LogoutView(APIView):
    permission_classes = [] # Allow anyone to call logout to clear local cookies
    
    def post(self, request):
        response = Response({"detail": "Logged out"}, status=status.HTTP_200_OK)
        
        # Blacklist refresh token if provided
        refresh_token = request.COOKIES.get(settings.SIMPLE_JWT.get("REFRESH_COOKIE", "refresh_token"))
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except Exception:
                pass

        response.delete_cookie(settings.SIMPLE_JWT.get("AUTH_COOKIE", "access_token"))
        response.delete_cookie(settings.SIMPLE_JWT.get("REFRESH_COOKIE", "refresh_token"))
        return response
