# Drops standalone weekly meal plan; wellness meals use Meal.wellness_plan only.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("nutrition", "0005_weeklyWellnessPlan"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="meal",
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name="meal",
            name="meal_plan",
        ),
        migrations.DeleteModel(
            name="WeeklyMealPlan",
        ),
        migrations.AlterUniqueTogether(
            name="meal",
            unique_together={("wellness_plan", "day_index", "meal_type")},
        ),
    ]
