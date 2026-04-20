from django.contrib import admin

from .models import ExerciseSession, FoodSubstitution, MealLog, NutritionGoal, RecoveryPlan

admin.site.register(MealLog)
admin.site.register(NutritionGoal)
admin.site.register(FoodSubstitution)
admin.site.register(ExerciseSession)
admin.site.register(RecoveryPlan)
