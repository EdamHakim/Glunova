from django.core.management import call_command
from django.test import TestCase

from carecircle.models import Appointment, FamilyUpdate
from users.models import PatientDoctorLink
from clinical.models import ClinicalCaseReview, CrisisEscalation, ImagingAnalysis
from kids.models import KidsInteraction
from monitoring.models import DiseaseProgression, HealthAlert, PatientMedication, RiskAssessment
from nutrition.models import ExerciseSession, NutritionGoal, RecoveryPlan
from psychology.models import EmotionAssessment, TherapySession
from screening.models import AIExplanation, ScreeningResult


class SyntheticDatasetCommandTests(TestCase):
    def test_command_generates_core_entities(self):
        call_command("generate_synthetic_datasets")

        self.assertEqual(ScreeningResult.objects.count(), 15)
        self.assertEqual(RiskAssessment.objects.count(), 15)
        self.assertEqual(HealthAlert.objects.count(), 15)
        self.assertEqual(DiseaseProgression.objects.count(), 15)
        self.assertEqual(NutritionGoal.objects.count(), 5)
        self.assertEqual(ExerciseSession.objects.count(), 5)
        self.assertEqual(RecoveryPlan.objects.count(), 5)
        self.assertEqual(EmotionAssessment.objects.count(), 5)
        self.assertEqual(TherapySession.objects.count(), 5)
        self.assertEqual(CrisisEscalation.objects.count(), 5)
        self.assertEqual(KidsInteraction.objects.count(), 5)
        self.assertEqual(FamilyUpdate.objects.count(), 5)
        self.assertEqual(Appointment.objects.count(), 5)
        self.assertEqual(PatientDoctorLink.objects.count(), 5)
        self.assertEqual(ClinicalCaseReview.objects.count(), 5)
        self.assertEqual(ImagingAnalysis.objects.count(), 5)
        self.assertEqual(PatientMedication.objects.count(), 5)
        self.assertEqual(AIExplanation.objects.count(), 5)
