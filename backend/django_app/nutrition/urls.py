from django.urls import path

from .views import (
    ExercisePlanListView,
    ExerciseStatusView,
    MealStatusView,
    WellnessPlanCurrentView,
    WellnessPlanDetailView,
    WellnessPlanGenerateView,
    WellnessPlanRegenerateDayView,
)

urlpatterns = [
    # Standalone exercise sessions (legacy)
    path("nutrition/exercise",                              ExercisePlanListView.as_view(),            name="nutrition-exercise"),
    # Item-level status toggles
    path("nutrition/exercise/<int:pk>/status",              ExerciseStatusView.as_view(),              name="nutrition-exercise-status"),
    path("nutrition/meal/<int:pk>/status",                  MealStatusView.as_view(),                  name="nutrition-meal-status"),
    # Weekly wellness plan (exercise + meals unified)
    path("nutrition/wellness-plan/generate",                WellnessPlanGenerateView.as_view(),        name="wellness-plan-generate"),
    path("nutrition/wellness-plan/current",                 WellnessPlanCurrentView.as_view(),         name="wellness-plan-current"),
    path("nutrition/wellness-plan/<int:pk>",                WellnessPlanDetailView.as_view(),          name="wellness-plan-detail"),
    path("nutrition/wellness-plan/<int:pk>/regenerate-day", WellnessPlanRegenerateDayView.as_view(),   name="wellness-plan-regenerate-day"),
]
