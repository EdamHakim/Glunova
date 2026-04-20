from django.conf import settings
from django.db import models


class KidsInteraction(models.Model):
    class Feature(models.TextChoices):
        SPEECH_ASSISTANT = "speech_assistant", "AI Speech Assistant"
        LIE_DETECTION = "lie_detection", "Lie Detection via Expressions"
        VOICE_CLONING = "voice_cloning", "Voice Cloning"
        STORYMAKER = "storymaker", "StoryMaker"
        QUIZ = "quiz", "Gamified Learning"

    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="kids_interactions")
    feature = models.CharField(max_length=32, choices=Feature.choices)
    interaction_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
