from django.db import migrations


class Migration(migrations.Migration):
    """
    Remove PatientCaregiverLink from the documents app Django state.
    The DB table is NOT touched — it is re-registered under the users app
    in users/0006_add_link_models.py using SeparateDatabaseAndState.
    """

    dependencies = [
        ("documents", "0001_initial"),
        # users/0006 must run first so the table is already claimed before
        # we drop it from the documents state.
        ("users", "0006_add_link_models"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveConstraint(
                    model_name="patientcaregiverlink",
                    name="uniq_patient_caregiver_document_link",
                ),
                migrations.DeleteModel(name="PatientCaregiverLink"),
            ],
            database_operations=[],  # table stays; users app now owns it
        ),
    ]
