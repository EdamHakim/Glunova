from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("nutrition", "0006_remove_weekly_meal_plan"),
    ]

    operations = [
        migrations.AddField(
            model_name="meal",
            name="status",
            field=models.CharField(
                choices=[("planned", "Planned"), ("completed", "Completed"), ("skipped", "Skipped")],
                default="planned",
                max_length=16,
            ),
        ),
    ]
