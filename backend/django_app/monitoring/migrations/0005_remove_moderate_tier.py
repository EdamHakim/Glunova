"""Remove the MODERATE tier from RiskAssessment.

Glunova fusion v11 (late_fusion_robust) only emits LOW / HIGH / CRITICAL.
The MODERATE tier was a leftover from an earlier 4-tier design and was never
produced by the predictor. We:
  1. Migrate any legacy 'moderate' rows to 'high' (conservative: do not silently
     downgrade existing risk records to LOW).
  2. Update the field choices to drop MODERATE.
"""
from django.db import migrations, models


def migrate_moderate_to_high(apps, schema_editor):
    RiskAssessment = apps.get_model("monitoring", "RiskAssessment")
    RiskAssessment.objects.filter(tier="moderate").update(tier="high")


def revert_high_unchanged(apps, schema_editor):
    """No-op reverse: we cannot recover which 'high' rows used to be 'moderate'."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("monitoring", "0004_patientmedication_instructions"),
    ]

    operations = [
        migrations.RunPython(migrate_moderate_to_high, revert_high_unchanged),
        migrations.AlterField(
            model_name="riskassessment",
            name="tier",
            field=models.CharField(
                choices=[
                    ("low", "Low"),
                    ("high", "High"),
                    ("critical", "Critical"),
                ],
                max_length=16,
            ),
        ),
    ]
