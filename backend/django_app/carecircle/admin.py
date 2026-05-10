from django.contrib import admin

from .models import Appointment, AppointmentSlot, FamilyUpdate

admin.site.register(FamilyUpdate)
admin.site.register(Appointment)
admin.site.register(AppointmentSlot)
