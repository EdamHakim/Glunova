from django.contrib import admin

from .models import Appointment, AppointmentSlot, DoctorAvailability, FamilyUpdate

admin.site.register(FamilyUpdate)
admin.site.register(Appointment)
admin.site.register(AppointmentSlot)
admin.site.register(DoctorAvailability)
