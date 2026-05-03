from django.urls import path

from .views import (
    ExercisePlanListView,
    MealPlanCurrentView,
    MealPlanDetailView,
    MealPlanGenerateView,
    MealPlanRegenerateDayView,
)

urlpatterns = [
    path("nutrition/exercise",                          ExercisePlanListView.as_view(),       name="nutrition-exercise"),
    path("nutrition/meal-plan/generate",                MealPlanGenerateView.as_view(),        name="meal-plan-generate"),
    path("nutrition/meal-plan/current",                 MealPlanCurrentView.as_view(),         name="meal-plan-current"),
    path("nutrition/meal-plan/<int:pk>",                MealPlanDetailView.as_view(),          name="meal-plan-detail"),
    path("nutrition/meal-plan/<int:pk>/regenerate-day", MealPlanRegenerateDayView.as_view(),   name="meal-plan-regenerate-day"),
]
