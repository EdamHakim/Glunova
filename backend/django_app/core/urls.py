from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from core.auth_views import GlunovaTokenObtainPairView, RegisterView, LogoutView, GlunovaTokenRefreshView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/register/", RegisterView.as_view(), name="register"),
    path("api/auth/token/", GlunovaTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", GlunovaTokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/logout/", LogoutView.as_view(), name="logout"),
    path("api/v1/", include("documents.urls")),
    path("api/v1/", include("clinical.urls")),
    path("api/v1/", include("monitoring.urls")),
    path("api/v1/", include("nutrition.urls")),
    path("api/v1/", include("carecircle.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
