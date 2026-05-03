from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("nutrition", "0003_weeklymealplan_meal"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="meal",
            name="nutritional_source",
        ),
        migrations.RemoveField(
            model_name="meal",
            name="usda_breakdown",
        ),
    ]
