from django.contrib import admin

from .models import (
    ClinicalCaseReview,
    CrisisEscalation,
    ImagingAnalysis,
)
admin.site.register(CrisisEscalation)
admin.site.register(ClinicalCaseReview)
admin.site.register(ImagingAnalysis)
