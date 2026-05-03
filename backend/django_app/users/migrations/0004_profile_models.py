from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def forward_create_profiles(apps, schema_editor):
    User = apps.get_model("users", "User")
    PatientProfile = apps.get_model("users", "PatientProfile")
    DoctorProfile = apps.get_model("users", "DoctorProfile")
    CaregiverProfile = apps.get_model("users", "CaregiverProfile")

    for user in User.objects.all():
        if user.role == "patient":
            PatientProfile.objects.get_or_create(
                user=user,
                defaults={
                    "date_of_birth":      user.date_of_birth,
                    "gender":             user.gender,
                    "height_cm":          user.height_cm,
                    "weight_kg":          user.weight_kg,
                    "hypertension":       user.hypertension,
                    "heart_disease":      user.heart_disease,
                    "smoking_status":     user.smoking_status,
                    "hba1c_level":        user.hba1c_level,
                    "blood_glucose_level": user.blood_glucose_level,
                    "diabetes_type":      "Type 2",
                    "allergies":          [],
                },
            )
        elif user.role == "doctor":
            DoctorProfile.objects.get_or_create(user=user)
        elif user.role == "caregiver":
            CaregiverProfile.objects.get_or_create(user=user)


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0003_user_profile_picture"),
    ]

    operations = [
        # 1. Create the three profile tables
        migrations.CreateModel(
            name="PatientProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date_of_birth", models.DateField(blank=True, null=True)),
                ("gender", models.CharField(
                    blank=True,
                    choices=[("Male", "Male"), ("Female", "Female")],
                    max_length=10,
                    null=True,
                )),
                ("height_cm", models.DecimalField(blank=True, decimal_places=1, max_digits=5, null=True)),
                ("weight_kg", models.DecimalField(blank=True, decimal_places=1, max_digits=5, null=True)),
                ("hypertension", models.BooleanField(blank=True, null=True)),
                ("heart_disease", models.BooleanField(blank=True, null=True)),
                ("smoking_status", models.CharField(
                    blank=True,
                    choices=[
                        ("never", "Never"),
                        ("former", "Former"),
                        ("current", "Current"),
                        ("ever", "Ever"),
                        ("not current", "Not current"),
                        ("No Info", "No info"),
                    ],
                    max_length=20,
                    null=True,
                )),
                ("diabetes_type", models.CharField(
                    choices=[
                        ("Type 1", "Type 1"),
                        ("Type 2", "Type 2"),
                        ("Gestational", "Gestational"),
                        ("Prediabetes", "Prediabetes"),
                    ],
                    default="Type 2",
                    max_length=20,
                )),
                ("hba1c_level", models.DecimalField(blank=True, decimal_places=2, max_digits=4, null=True)),
                ("blood_glucose_level", models.IntegerField(blank=True, null=True)),
                ("allergies", models.JSONField(default=list)),
                ("user", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="patient_profile",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
        ),
        migrations.CreateModel(
            name="DoctorProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("specialization", models.CharField(blank=True, max_length=100)),
                ("license_number", models.CharField(blank=True, max_length=64)),
                ("hospital_affiliation", models.CharField(blank=True, max_length=200)),
                ("user", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="doctor_profile",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
        ),
        migrations.CreateModel(
            name="CaregiverProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("relationship", models.CharField(blank=True, max_length=50)),
                ("is_professional", models.BooleanField(default=False)),
                ("user", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="caregiver_profile",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
        ),
        # 2. Copy existing patient data from User rows to PatientProfile
        migrations.RunPython(forward_create_profiles, migrations.RunPython.noop),
        # 3. Remove health fields from the User table
        migrations.RemoveField(model_name="user", name="date_of_birth"),
        migrations.RemoveField(model_name="user", name="gender"),
        migrations.RemoveField(model_name="user", name="height_cm"),
        migrations.RemoveField(model_name="user", name="weight_kg"),
        migrations.RemoveField(model_name="user", name="hypertension"),
        migrations.RemoveField(model_name="user", name="heart_disease"),
        migrations.RemoveField(model_name="user", name="smoking_status"),
        migrations.RemoveField(model_name="user", name="hba1c_level"),
        migrations.RemoveField(model_name="user", name="blood_glucose_level"),
    ]
