from django.contrib import admin

from .models import (
    KidsDailyCheckin,
    KidsInstructionChunk,
    KidsInstructionDocument,
    KidsInteraction,
    KidsProfile,
    KidsStorySession,
)

admin.site.register(KidsInteraction)
admin.site.register(KidsProfile)
admin.site.register(KidsInstructionDocument)
admin.site.register(KidsInstructionChunk)
admin.site.register(KidsDailyCheckin)
admin.site.register(KidsStorySession)
