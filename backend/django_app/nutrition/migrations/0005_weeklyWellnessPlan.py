from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("nutrition", "0004_remove_meal_usda_fields"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Create WeeklyWellnessPlan
        migrations.CreateModel(
            name="WeeklyWellnessPlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("week_start",        models.DateField()),
                ("status",            models.CharField(choices=[("pending", "Pending"), ("ready", "Ready"), ("failed", "Failed")], default="pending", max_length=20)),
                ("fitness_level",     models.CharField(blank=True, max_length=20)),
                ("goal",              models.CharField(blank=True, max_length=30)),
                ("cuisine",           models.CharField(blank=True, max_length=30)),
                ("generated_at",      models.DateTimeField(blank=True, null=True)),
                ("clinical_snapshot", models.JSONField(default=dict)),
                ("week_summary",      models.JSONField(default=dict)),
                ("patient",           models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="wellness_plans", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-week_start"]},
        ),
        migrations.AlterUniqueTogether(
            name="weeklyWellnessPlan".lower(),
            unique_together={("patient", "week_start")},
        ),
        # 2. Add wellness-plan FK + new fields to ExerciseSession
        migrations.AddField(
            model_name="exercisesession",
            name="wellness_plan",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="exercise_sessions", to="nutrition.weeklyWellnessPlan".lower()),
        ),
        migrations.AddField(model_name="exercisesession", name="day_index",        field=models.PositiveSmallIntegerField(blank=True, null=True)),
        migrations.AddField(model_name="exercisesession", name="exercise_type",    field=models.CharField(blank=True, max_length=30)),
        migrations.AddField(model_name="exercisesession", name="description",      field=models.TextField(blank=True)),
        migrations.AddField(model_name="exercisesession", name="sets",             field=models.PositiveSmallIntegerField(blank=True, null=True)),
        migrations.AddField(model_name="exercisesession", name="reps",             field=models.PositiveSmallIntegerField(blank=True, null=True)),
        migrations.AddField(model_name="exercisesession", name="equipment",        field=models.JSONField(default=list)),
        migrations.AddField(model_name="exercisesession", name="pre_exercise_glucose_check", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="exercisesession", name="post_exercise_snack_tip",    field=models.TextField(blank=True)),
        migrations.AddField(model_name="exercisesession", name="diabetes_rationale",         field=models.TextField(blank=True)),
        # 3. Add wellness-plan FK to Meal + allow meal_plan to be nullable + new meal types
        migrations.AddField(
            model_name="meal",
            name="wellness_plan",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="meals", to="nutrition.weeklyWellnessPlan".lower()),
        ),
        migrations.AlterField(
            model_name="meal",
            name="meal_plan",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="meals", to="nutrition.weeklymealplan"),
        ),
        migrations.AlterField(
            model_name="meal",
            name="meal_type",
            field=models.CharField(
                choices=[
                    ("breakfast", "Breakfast"), ("lunch", "Lunch"),
                    ("dinner", "Dinner"), ("snack", "Snack"),
                    ("pre_workout_snack", "Pre-Workout Snack"),
                    ("post_workout_snack", "Post-Workout Snack"),
                ],
                max_length=20,
            ),
        ),
    ]
