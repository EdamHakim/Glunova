# Generated manually for psychology AI persistence layer

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("psychology", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PsychologyProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("health_context_json", models.JSONField(blank=True, default=dict)),
                ("personality_notes", models.TextField(blank=True)),
                ("preferred_language", models.CharField(default="en", max_length=16)),
                ("physician_review_required", models.BooleanField(default=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="psychology_profile",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Psychology profile",
                "verbose_name_plural": "Psychology profiles",
            },
        ),
        migrations.CreateModel(
            name="PsychologySession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("session_id", models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ("preferred_language", models.CharField(default="en", max_length=16)),
                ("started_at", models.DateTimeField()),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                ("last_state", models.CharField(blank=True, max_length=32)),
                ("crisis_score_history_json", models.JSONField(blank=True, default=list)),
                ("session_summary_json", models.JSONField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "patient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="psychology_ai_sessions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-started_at", "-created_at"],
            },
        ),
        migrations.CreateModel(
            name="PsychologyMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(max_length=16)),
                ("content", models.TextField()),
                ("created_at", models.DateTimeField()),
                ("fusion_metadata", models.JSONField(blank=True, null=True)),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="messages",
                        to="psychology.psychologysession",
                    ),
                ),
            ],
            options={
                "ordering": ["created_at", "id"],
            },
        ),
        migrations.CreateModel(
            name="PsychologyCrisisEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("probability", models.FloatField()),
                ("action_taken", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("acknowledged_at", models.DateTimeField(blank=True, null=True)),
                (
                    "patient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="psychology_crisis_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "session",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="crisis_events",
                        to="psychology.psychologysession",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="PsychologyEmotionLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("logged_at", models.DateTimeField(db_index=True)),
                ("distress_score", models.FloatField()),
                ("mental_state", models.CharField(max_length=32)),
                (
                    "patient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="psychology_emotion_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-logged_at"],
            },
        ),
        migrations.AddIndex(
            model_name="psychologyemotionlog",
            index=models.Index(fields=["patient", "logged_at"], name="psychology_p_patient_idx"),
        ),
    ]
