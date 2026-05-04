from rest_framework import serializers

from .models import KidsDailyCheckin, KidsProfile, KidsStorySession


class KidsProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = KidsProfile
        fields = [
            "assistant_name",
            "persona_prompt",
            "avatar_prompt",
            "avatar_image_url",
            "parent_voice_sample_url",
            "parent_voice_profile_id",
            "child_reference_photos",
            "story_preferences",
            "updated_at",
        ]


class KidsCheckinSerializer(serializers.Serializer):
    child_message = serializers.CharField(max_length=2500, allow_blank=True, required=False)
    followed_instructions = serializers.BooleanField()
    lie_risk_score = serializers.FloatField(min_value=0.0, max_value=1.0, required=False, default=0.0)


class KidsStoryRequestSerializer(serializers.Serializer):
    checkin_id = serializers.IntegerField(required=False)
    prompt = serializers.CharField(max_length=2500, allow_blank=True, required=False)


class KidsAssistantMessageSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=2500, allow_blank=True, required=False)


class KidsDailyCheckinSerializer(serializers.ModelSerializer):
    class Meta:
        model = KidsDailyCheckin
        fields = ["id", "child_message", "followed_instructions", "lie_risk_score", "assistant_feedback", "created_at"]


class KidsStorySessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = KidsStorySession
        fields = [
            "id",
            "checkin_id",
            "mood",
            "title",
            "narrative",
            "scene_image_prompt",
            "scene_image_url",
            "protagonist_face_refs",
            "metadata",
            "created_at",
        ]
