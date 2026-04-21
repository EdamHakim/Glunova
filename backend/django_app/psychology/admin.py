from django.contrib import admin

from .models import (
    EmotionAssessment,
    PsychologyCrisisEvent,
    PsychologyEmotionLog,
    PsychologyMessage,
    PsychologyProfile,
    PsychologySession,
    TherapySession,
)


@admin.register(PsychologyProfile)
class PsychologyProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "preferred_language", "physician_review_required", "updated_at")
    search_fields = ("user__email", "personality_notes")


class PsychologyMessageInline(admin.TabularInline):
    model = PsychologyMessage
    extra = 0
    readonly_fields = ("created_at", "fusion_metadata")


@admin.register(PsychologySession)
class PsychologySessionAdmin(admin.ModelAdmin):
    list_display = ("session_id", "patient", "preferred_language", "started_at", "ended_at", "last_state")
    list_filter = ("preferred_language",)
    search_fields = ("session_id",)
    inlines = [PsychologyMessageInline]


@admin.register(PsychologyCrisisEvent)
class PsychologyCrisisEventAdmin(admin.ModelAdmin):
    list_display = ("id", "patient", "probability", "created_at", "acknowledged_at")
    list_filter = ("acknowledged_at",)


@admin.register(PsychologyEmotionLog)
class PsychologyEmotionLogAdmin(admin.ModelAdmin):
    list_display = ("patient", "logged_at", "distress_score", "mental_state")


admin.site.register(EmotionAssessment)
admin.site.register(TherapySession)
