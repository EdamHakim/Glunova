from django.urls import path

from .views import (
    KidsAvatarGenerateView,
    KidsAssistantHistoryView,
    KidsAssistantMessageView,
    KidsChildPhotoUploadView,
    KidsDailyCheckinView,
    KidsDoctorInstructionUploadView,
    KidsParentVoiceUploadView,
    KidsParentVoiceSynthesizeView,
    KidsProfileView,
    KidsRagContextView,
    KidsStateView,
    KidsStoryGenerateView,
    KidsLieDetectorView,
)

urlpatterns = [
    path("kids/profile", KidsProfileView.as_view(), name="kids-profile"),
    path("kids/assistant/message", KidsAssistantMessageView.as_view(), name="kids-assistant-message"),
    path("kids/assistant/history", KidsAssistantHistoryView.as_view(), name="kids-assistant-history"),
    path("kids/avatar/generate", KidsAvatarGenerateView.as_view(), name="kids-avatar-generate"),
    path("kids/parent-voice/upload", KidsParentVoiceUploadView.as_view(), name="kids-parent-voice-upload"),
    path("kids/parent-voice/synthesize", KidsParentVoiceSynthesizeView.as_view(), name="kids-parent-voice-synthesize"),
    path("kids/child-photos/upload", KidsChildPhotoUploadView.as_view(), name="kids-child-photo-upload"),
    path("kids/instructions/upload", KidsDoctorInstructionUploadView.as_view(), name="kids-instructions-upload"),
    path("kids/rag-context", KidsRagContextView.as_view(), name="kids-rag-context"),
    path("kids/checkin", KidsDailyCheckinView.as_view(), name="kids-checkin"),
    path("kids/story/generate", KidsStoryGenerateView.as_view(), name="kids-story-generate"),
    path("kids/lie-detect", KidsLieDetectorView.as_view(), name="kids-lie-detect"),
    path("kids/state", KidsStateView.as_view(), name="kids-state"),
]
