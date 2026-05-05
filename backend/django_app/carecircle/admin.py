from django.contrib import admin

from .models import Appointment, FamilyUpdate

admin.site.register(FamilyUpdate)
admin.site.register(Appointment)
