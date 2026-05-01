import os
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parent / "models" / "retinopathy"

V51_CHECKPOINT_NAME = "best_v5_1.pt"
V8_CHECKPOINT_NAME = "best_v8.pt"


def resolve_v51_pt_path() -> Path:
    """Resolved at use time so backend/.env is applied reliably."""
    env = os.environ.get("DR_V51_PT_PATH")
    if env:
        return Path(env)
    return MODEL_DIR / V51_CHECKPOINT_NAME


def resolve_v8_pt_path() -> Path:
    env = os.environ.get("DR_V8_PT_PATH")
    if env:
        return Path(env)
    return MODEL_DIR / V8_CHECKPOINT_NAME


# ─── V5.1 binary (No DR vs DR) — EfficientNetV2-S ────────────────────────────
V51_BACKBONE = "tf_efficientnetv2_s.in21k_ft_in1k"
V51_INPUT_SIZE = 512
V51_NUM_CLASSES = 2
V51_IN_CHANS = 3
V51_NORM_MEAN = (0.485, 0.456, 0.406)
V51_NORM_STD = (0.229, 0.224, 0.225)
# Youden J threshold from validation set (glunova_binary_inference.py).
V51_DEFAULT_THRESHOLD = float(os.environ.get("DR_V51_THRESHOLD", "0.546"))
V51_CLASS_NAMES = ("No DR", "DR")
V51_MODEL_NAME = "efficientnetv2s_dr_binary"
V51_MODEL_VERSION = "v5.1"


# ─── V8 severity (4-class NPDR/PDR) — ConvNeXt-Base + TriplePool ─────────────
V8_BACKBONE = "convnext_base.fb_in22k_ft_in1k"
V8_INPUT_SIZE = 728
V8_NUM_CLASSES = 4
V8_IN_CHANS = 4  # RGB + CLAHE-enhanced green
V8_NORM_MEAN = (0.485, 0.456, 0.406, 0.5)
V8_NORM_STD = (0.229, 0.224, 0.225, 0.25)
V8_GRADE_NAMES = ("Mild", "Moderate", "Severe", "Proliferative")
V8_MODEL_NAME = "convnext_base_triplepool_dr_severity"
V8_MODEL_VERSION = "v8"


# ─── Cascade output (ICDR clinical grading 0..4) ─────────────────────────────
# V5.1 says "No DR" -> clinical 0; V5.1 says "DR" -> V8 grade_idx 0..3 maps to clinical 1..4.
CLINICAL_GRADE_LABELS = (
    "No DR",
    "Mild NPDR",
    "Moderate NPDR",
    "Severe NPDR",
    "Proliferative DR",
)
