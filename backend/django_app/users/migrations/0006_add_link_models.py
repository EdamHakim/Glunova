import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    1. Claim PatientCaregiverLink from the documents app:
       - State: register the full model (with invitation fields) under users.
       - DB: add the two new columns (status, responded_at) to the existing
         documents_patientcaregiverlink table via raw SQL so no data is lost.
         Existing rows are back-filled with status='accepted' (they were
         already active links).
    2. Create PatientDoctorLink as a brand-new table.
    """

    dependencies = [
        ("users", "0005_alter_patientprofile_diabetes_type"),
        # Ensure the documents table already exists before we touch it.
        ("documents", "0001_initial"),
    ]

    operations = [
        # ── PatientCaregiverLink ──────────────────────────────────────────────
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="PatientCaregiverLink",
                    fields=[
                        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                        ("status", models.CharField(
                            choices=[("pending", "Pending"), ("accepted", "Accepted"), ("rejected", "Rejected")],
                            default="pending",
                            max_length=16,
                        )),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        ("responded_at", models.DateTimeField(blank=True, null=True)),
                        ("caregiver", models.ForeignKey(
                            on_delete=django.db.models.deletion.CASCADE,
                            related_name="patient_links_as_caregiver",
                            to=settings.AUTH_USER_MODEL,
                        )),
                        ("patient", models.ForeignKey(
                            on_delete=django.db.models.deletion.CASCADE,
                            related_name="caregiver_links",
                            to=settings.AUTH_USER_MODEL,
                        )),
                    ],
                    options={"db_table": "documents_patientcaregiverlink"},
                ),
                migrations.AddConstraint(
                    model_name="patientcaregiverlink",
                    constraint=models.UniqueConstraint(
                        fields=("patient", "caregiver"),
                        name="uniq_patient_caregiver_document_link",
                    ),
                ),
            ],
            database_operations=[
                # Add only the two new columns; all other columns already exist.
                # Default 'accepted' back-fills existing rows as already-accepted links.
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE documents_patientcaregiverlink
                            ADD COLUMN IF NOT EXISTS status VARCHAR(16) NOT NULL DEFAULT 'accepted';
                    """,
                    reverse_sql="ALTER TABLE documents_patientcaregiverlink DROP COLUMN IF EXISTS status;",
                ),
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE documents_patientcaregiverlink
                            ADD COLUMN IF NOT EXISTS responded_at TIMESTAMPTZ NULL;
                    """,
                    reverse_sql="ALTER TABLE documents_patientcaregiverlink DROP COLUMN IF EXISTS responded_at;",
                ),
            ],
        ),

        # ── PatientDoctorLink ─────────────────────────────────────────────────
        migrations.CreateModel(
            name="PatientDoctorLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("linked_at", models.DateTimeField(auto_now_add=True)),
                ("patient", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="doctor_links",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("doctor", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="patient_links_as_doctor",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
        ),
        migrations.AddConstraint(
            model_name="patientdoctorlink",
            constraint=models.UniqueConstraint(
                fields=("patient", "doctor"),
                name="uniq_patient_doctor_link",
            ),
        ),
    ]
