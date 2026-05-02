# Generated manually for Sanadi 3-layer memory (semantic Postgres layer).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("psychology", "0003_rename_psychology_p_patient_idx_psychology__patient_4f645a_idx"),
    ]

    operations = [
        migrations.AddField(
            model_name="psychologyprofile",
            name="semantic_profile_json",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
