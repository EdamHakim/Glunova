from django.urls import path

from .views import (
    ExercisePlanListView,
    MealPlanCurrentView,
    MealPlanDetailView,
    MealPlanGenerateView,
    MealPlanRegenerateDayView,
    WellnessPlanCurrentView,
    WellnessPlanDetailView,
    WellnessPlanGenerateView,
    WellnessPlanRegenerateDayView,
)

urlpatterns = [
    # Standalone exercise sessions (legacy)
    path("nutrition/exercise",                              ExercisePlanListView.as_view(),            name="nutrition-exercise"),
    # Meal plan only
    path("nutrition/meal-plan/generate",                    MealPlanGenerateView.as_view(),            name="meal-plan-generate"),
    path("nutrition/meal-plan/current",                     MealPlanCurrentView.as_view(),             name="meal-plan-current"),
    path("nutrition/meal-plan/<int:pk>",                    MealPlanDetailView.as_view(),              name="meal-plan-detail"),
    path("nutrition/meal-plan/<int:pk>/regenerate-day",     MealPlanRegenerateDayView.as_view(),       name="meal-plan-regenerate-day"),
    # Weekly wellness plan (exercise + meals unified)
    path("nutrition/wellness-plan/generate",                WellnessPlanGenerateView.as_view(),        name="wellness-plan-generate"),
    path("nutrition/wellness-plan/current",                 WellnessPlanCurrentView.as_view(),         name="wellness-plan-current"),
    path("nutrition/wellness-plan/<int:pk>",                WellnessPlanDetailView.as_view(),          name="wellness-plan-detail"),
    path("nutrition/wellness-plan/<int:pk>/regenerate-day", WellnessPlanRegenerateDayView.as_view(),   name="wellness-plan-regenerate-day"),
]
