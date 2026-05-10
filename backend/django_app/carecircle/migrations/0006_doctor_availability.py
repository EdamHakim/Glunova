from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("carecircle", "0005_appointment_slot_and_booking_link"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DoctorAvailability",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("day_of_week", models.IntegerField(choices=[(0, "Monday"), (1, "Tuesday"), (2, "Wednesday"), (3, "Thursday"), (4, "Friday"), (5, "Saturday"), (6, "Sunday")])),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                ("slot_duration_min", models.IntegerField(default=30)),
                ("lunch_start", models.TimeField(blank=True, null=True)),
                ("lunch_end", models.TimeField(blank=True, null=True)),
                ("doctor", models.ForeignKey(limit_choices_to={"role": "doctor"}, on_delete=django.db.models.deletion.CASCADE, related_name="availabilities", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["day_of_week"],
                "unique_together": {("doctor", "day_of_week")},
            },
        ),
    ]
