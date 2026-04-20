from django.contrib import admin

from .models import Appointment, CarePlan, CareTask, FamilyUpdate, MedicationGuidance

admin.site.register(CarePlan)
admin.site.register(FamilyUpdate)
admin.site.register(CareTask)
admin.site.register(Appointment)
admin.site.register(MedicationGuidance)
