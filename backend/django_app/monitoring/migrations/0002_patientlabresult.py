from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0001_initial"),
        ("monitoring", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PatientLabResult",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("test_name", models.CharField(max_length=255)),
                ("normalized_name", models.CharField(blank=True, max_length=255)),
                ("value", models.CharField(max_length=64)),
                ("numeric_value", models.FloatField(blank=True, null=True)),
                ("unit", models.CharField(blank=True, max_length=64, null=True)),
                ("reference_range", models.CharField(blank=True, max_length=255, null=True)),
                ("observed_at", models.DateTimeField(blank=True, null=True)),
                ("raw_payload", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "patient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="patient_lab_results",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "source_document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="patient_lab_results",
                        to="documents.medicaldocument",
                    ),
                ),
            ],
            options={
                "ordering": ["-observed_at", "-updated_at", "-created_at", "id"],
            },
        ),
    ]
