from django.contrib import admin
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from core.auth_views import GlunovaTokenObtainPairView, RegisterView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/register/", RegisterView.as_view(), name="register"),
    path("api/auth/token/", GlunovaTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]
