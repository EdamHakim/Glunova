from __future__ import annotations

import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from carecircle.models import Appointment, CarePlan, CareTask, FamilyUpdate, MedicationGuidance
from clinical.models import ClinicalCaseReview, CrisisEscalation, ImagingAnalysis
from documents.models import MedicalDocument
from users.models import PatientCaregiverLink
from kids.models import KidsInteraction
from monitoring.models import DiseaseProgression, HealthAlert, MonitoringLog, PatientMedication, RiskAssessment
from nutrition.models import ExerciseSession, NutritionGoal, RecoveryPlan
from psychology.models import EmotionAssessment, TherapySession
from screening.models import AIExplanation, ScreeningResult

User = get_user_model()


class Command(BaseCommand):
    help = "Generate deterministic synthetic clinical datasets for testing."

    @transaction.atomic
    def handle(self, *args, **options):
        rnd = random.Random(2026)
        now = timezone.now()

        doctor, _ = User.objects.get_or_create(
            username="doctor.synthetic",
            defaults={"email": "doctor.synthetic@glunova.local", "role": "doctor"},
        )
        doctor.set_password("doctor.synthetic")
        doctor.save(update_fields=["password"])

        caregiver, _ = User.objects.get_or_create(
            username="caregiver.synthetic",
            defaults={"email": "caregiver.synthetic@glunova.local", "role": "caregiver"},
        )
        caregiver.set_password("caregiver.synthetic")
        caregiver.save(update_fields=["password"])

        patients: list[User] = []
        for index in range(1, 6):
            patient, _ = User.objects.get_or_create(
                username=f"patient.synthetic.{index}",
                defaults={
                    "email": f"patient.synthetic.{index}@glunova.local",
                    "role": "patient",
                    "first_name": f"Patient{index}",
                    "last_name": "Synthetic",
                },
            )
            patient.set_password("patient.synthetic")
            patient.save(update_fields=["password"])
            patients.append(patient)

            PatientCaregiverLink.objects.get_or_create(patient=patient, caregiver=caregiver)

        modalities = list(ScreeningResult.Modality.values)
        imaging_types = list(ImagingAnalysis.AnalysisType.values)

        exercise_intensities = list(ExerciseSession.Intensity.values)
        distress_levels = list(EmotionAssessment.DistressLevel.values)
        risk_tiers = list(RiskAssessment.Tier.values)
        care_task_statuses = list(CareTask.Status.values)
        priorities = list(ClinicalCaseReview.Priority.values)

        for idx, patient in enumerate(patients, start=1):
            care_plan = CarePlan.objects.create(
                patient=patient,
                doctor=doctor,
                notes=f"Synthetic care plan for {patient.username}.",
            )

            for day_offset in range(3):
                captured_at = now - timedelta(days=day_offset * 3 + idx)
                modality = modalities[(idx + day_offset) % len(modalities)]
                score = round(rnd.uniform(0.2, 0.95), 3)

                ScreeningResult.objects.create(
                    patient=patient,
                    modality=modality,
                    score=score,
                    risk_label="high" if score >= 0.7 else "low",
                    model_version="synthetic-v1",
                    metadata={"sample_id": f"{patient.pk}-{day_offset}", "source": "synthetic"},
                    captured_at=captured_at,
                )

                risk = RiskAssessment.objects.create(
                    patient=patient,
                    tier=risk_tiers[(idx + day_offset) % len(risk_tiers)],
                    score=score,
                    confidence=round(rnd.uniform(0.7, 0.99), 3),
                    drivers=["screening", "lifestyle"],
                    assessed_at=captured_at + timedelta(hours=1),
                )

                HealthAlert.objects.create(
                    patient=patient,
                    risk_assessment=risk,
                    title=f"Risk threshold alert #{day_offset + 1}",
                    message="Synthetic alert generated for threshold-crossing workflow tests.",
                    severity=HealthAlert.Severity.CRITICAL if score >= 0.8 else HealthAlert.Severity.WARNING,
                    status=HealthAlert.Status.ACTIVE,
                    triggered_at=captured_at + timedelta(hours=2),
                )

                DiseaseProgression.objects.create(
                    patient=patient,
                    indicator="glycemic_risk_index",
                    value=round(rnd.uniform(0.1, 0.95), 3),
                    trend=DiseaseProgression.Trend.WORSENING if score >= 0.75 else DiseaseProgression.Trend.STABLE,
                    recorded_at=captured_at + timedelta(hours=3),
                    notes="Synthetic longitudinal progression sample.",
                )

                MonitoringLog.objects.create(
                    patient=patient,
                    source="synthetic_pipeline",
                    payload={
                        "risk_score": score,
                        "modality": modality,
                        "explanation": "Deterministic sample payload",
                    },
                )

            doc = MedicalDocument.objects.create(
                patient=patient,
                uploaded_by=patient,
                original_filename=f"synthetic_report_{idx}.pdf",
                mime_type="application/pdf",
                storage_path=f"synthetic/patient_{patient.pk}/report.pdf",
                processing_status=MedicalDocument.ProcessingStatus.COMPLETED,
                extracted_json={"kind": "lab_report", "origin": "synthetic"},
            )



            NutritionGoal.objects.create(
                patient=patient,
                target_calories_kcal=2000 - (idx * 70),
                target_carbs_g=220 - (idx * 12),
                target_protein_g=85 + (idx * 3),
                target_fat_g=65,
                target_sugar_g=35,
                valid_from=now.date() - timedelta(days=7),
                rationale="Synthetic adaptive target based on generated risk profile.",
            )



            exercise = ExerciseSession.objects.create(
                patient=patient,
                title="Brisk walk",
                intensity=exercise_intensities[idx % len(exercise_intensities)],
                duration_minutes=30 + idx * 5,
                scheduled_for=now + timedelta(days=idx),
                status=ExerciseSession.Status.PLANNED,
                notes="Synthetic glucose-aware schedule entry.",
            )
            RecoveryPlan.objects.create(
                exercise_session=exercise,
                snack_suggestion="Greek yogurt + berries",
                hydration_ml=500,
                glucose_recheck_minutes=30,
                next_session_tip="Gradually increase duration by 5 minutes.",
            )

            emotion = EmotionAssessment.objects.create(
                patient=patient,
                dominant_emotion="anxious" if idx % 2 == 0 else "calm",
                text_score=round(rnd.uniform(0.1, 0.95), 3),
                speech_score=round(rnd.uniform(0.1, 0.95), 3),
                facial_score=round(rnd.uniform(0.1, 0.95), 3),
                distress_level=distress_levels[idx % len(distress_levels)],
                summary="Synthetic multimodal emotion inference sample.",
                assessed_at=now - timedelta(hours=idx * 4),
            )

            TherapySession.objects.create(
                patient=patient,
                mode="sanadi",
                mood_before="stressed",
                mood_after="relieved",
                summary="Synthetic therapeutic dialogue summary.",
                started_at=now - timedelta(hours=idx * 5),
                ended_at=now - timedelta(hours=idx * 5 - 1),
            )

            CrisisEscalation.objects.create(
                patient=patient,
                emotion_assessment=emotion,
                physician=doctor,
                status=CrisisEscalation.Status.IN_REVIEW if idx % 2 == 0 else CrisisEscalation.Status.OPEN,
                summary="Synthetic physician escalation packet.",
            )

            KidsInteraction.objects.create(
                patient=patient,
                feature=KidsInteraction.Feature.STORYMAKER if idx % 2 == 0 else KidsInteraction.Feature.QUIZ,
                interaction_payload={"engagement_score": round(rnd.uniform(0.5, 0.98), 2)},
            )

            FamilyUpdate.objects.create(
                patient=patient,
                caregiver=caregiver,
                summary="Synthetic family update: stable progress with recommended meal adjustments.",
            )

            CareTask.objects.create(
                care_plan=care_plan,
                assignee=caregiver,
                title="Review meal adherence and hydration",
                status=care_task_statuses[idx % len(care_task_statuses)],
                due_at=now + timedelta(days=idx + 1),
            )

            Appointment.objects.create(
                patient=patient,
                doctor=doctor,
                caregiver=caregiver,
                title="Synthetic follow-up consultation",
                starts_at=now + timedelta(days=idx + 2),
                ends_at=now + timedelta(days=idx + 2, minutes=30),
                status=Appointment.Status.SCHEDULED,
                reminder_sent=(idx % 2 == 0),
            )

            MedicationGuidance.objects.create(
                patient=patient,
                requested_by=caregiver,
                medication_name="Metformin",
                guidance="Take with meals; monitor for GI discomfort; escalate severe side effects.",
                doctor_validated=(idx % 2 == 1),
            )

            ClinicalCaseReview.objects.create(
                patient=patient,
                priority=priorities[idx % len(priorities)],
                summary="Synthetic pre-consultation case brief with ranked urgency.",
                status=ClinicalCaseReview.Status.PENDING,
            )

            ImagingAnalysis.objects.create(
                patient=patient,
                analysis_type=imaging_types[idx % len(imaging_types)],
                severity_grade=idx % 5,
                confidence=round(rnd.uniform(0.6, 0.99), 3),
                findings={"lesions": rnd.randint(0, 8), "comment": "Synthetic imaging inference"},
                captured_at=now - timedelta(days=idx * 2),
            )

            AIExplanation.objects.create(
                patient=patient,
                context_type="risk_assessment",
                context_id=f"patient-{patient.pk}-latest",
                method="SHAP",
                technical_summary="Feature attribution indicates strongest impact from multimodal risk score.",
                plain_language_summary="Your current risk changed mainly because recent screening scores increased.",
            )

            PatientMedication.objects.create(
                patient=patient,
                source_document=doc,
                name_raw="metformin",
                name_display="Metformin 500 MG Oral Tablet",
                rxcui="860975",
                dosage="500mg",
                frequency="twice daily",
                route="oral",
                verification_status=PatientMedication.VerificationStatus.MATCHED,
            )

        self.stdout.write(self.style.SUCCESS("Synthetic clinical datasets generated successfully."))
