from django.contrib import admin

from .models import AIExplanation, ScreeningResult

admin.site.register(ScreeningResult)
admin.site.register(AIExplanation)
