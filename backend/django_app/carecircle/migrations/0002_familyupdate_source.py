from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("carecircle", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="familyupdate",
            name="source",
            field=models.CharField(
                choices=[("human", "Human"), ("agent", "Agent")],
                default="human",
                max_length=16,
            ),
        ),
    ]
