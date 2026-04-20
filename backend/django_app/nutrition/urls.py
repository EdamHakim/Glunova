from django.urls import path

from .views import ExercisePlanListView, MealLogListView, NutritionSummaryView

urlpatterns = [
    path("nutrition/summary", NutritionSummaryView.as_view(), name="nutrition-summary"),
    path("nutrition/meals", MealLogListView.as_view(), name="nutrition-meals"),
    path("nutrition/exercise", ExercisePlanListView.as_view(), name="nutrition-exercise"),
]
