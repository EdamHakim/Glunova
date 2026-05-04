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


class KidsProfile(models.Model):
    patient = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="kids_profile")
    persona_prompt = models.TextField(blank=True, default="")
    assistant_name = models.CharField(max_length=120, blank=True, default="Buddy")
    avatar_prompt = models.TextField(blank=True, default="")
    avatar_image_url = models.URLField(blank=True, default="")
    parent_voice_sample_url = models.URLField(blank=True, default="")
    parent_voice_profile_id = models.CharField(max_length=255, blank=True, default="")
    child_reference_photos = models.JSONField(default=list, blank=True)
    story_preferences = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]


class KidsInstructionDocument(models.Model):
    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="kids_instruction_docs")
    source_filename = models.CharField(max_length=255)
    document_text = models.TextField(blank=True, default="")
    extracted_rules = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class KidsInstructionChunk(models.Model):
    document = models.ForeignKey(KidsInstructionDocument, on_delete=models.CASCADE, related_name="chunks")
    chunk_text = models.TextField()
    token_set = models.JSONField(default=list, blank=True)
    sequence = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["document_id", "sequence"]
        unique_together = ("document", "sequence")


class KidsDailyCheckin(models.Model):
    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="kids_checkins")
    child_message = models.TextField(blank=True, default="")
    followed_instructions = models.BooleanField(default=False)
    lie_risk_score = models.FloatField(default=0.0)
    assistant_feedback = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class KidsAssistantTurn(models.Model):
    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="kids_assistant_turns")
    child_message = models.TextField(blank=True, default="")
    assistant_reply = models.TextField(blank=True, default="")
    checklist_state = models.JSONField(default=dict, blank=True)
    provider = models.CharField(max_length=64, blank=True, default="")
    model = models.CharField(max_length=120, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class KidsStorySession(models.Model):
    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="kids_story_sessions")
    checkin = models.ForeignKey(KidsDailyCheckin, null=True, blank=True, on_delete=models.SET_NULL)
    mood = models.CharField(max_length=16, default="neutral")
    title = models.CharField(max_length=255)
    narrative = models.TextField()
    scene_image_prompt = models.TextField(blank=True, default="")
    scene_image_url = models.URLField(blank=True, default="")
    protagonist_face_refs = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
