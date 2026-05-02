from django.urls import path

from .views import ExercisePlanListView

urlpatterns = [
    path("nutrition/exercise", ExercisePlanListView.as_view(), name="nutrition-exercise"),
]
