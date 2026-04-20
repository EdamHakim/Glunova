from django.contrib import admin

from .models import EmotionAssessment, TherapySession

admin.site.register(EmotionAssessment)
admin.site.register(TherapySession)
