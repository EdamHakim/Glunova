from django.contrib import admin

from .models import ExerciseSession, NutritionGoal, RecoveryPlan

admin.site.register(NutritionGoal)
admin.site.register(ExerciseSession)
admin.site.register(RecoveryPlan)
