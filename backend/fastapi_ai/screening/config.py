from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parent / "models" / "tongue"
PT_MODEL_PATH = MODEL_DIR / "resnet50_best.pt"

INPUT_SIZE = 224
NORM_MEAN = (0.485, 0.456, 0.406)
NORM_STD = (0.229, 0.224, 0.225)
DEFAULT_THRESHOLD = 0.5

CLASS_LABELS = {
    0: "nondiabetes",
    1: "diabetes",
}

MODEL_NAME = "resnet50_tongue_t2d"
MODEL_VERSION = "pt-v1"

# ─────────────────────────────────────────────────────────────
# CATARACT CONFIG (MobileNet - 4 classes)
# ─────────────────────────────────────────────────────────────

CATARACT_MODEL_DIR = Path(__file__).resolve().parent / "models" / "cataract"
CATARACT_PT_MODEL_PATH = CATARACT_MODEL_DIR / "BEST_mobilenet_final.pth"

CATARACT_INPUT_SIZE = 224
CATARACT_NORM_MEAN = (0.485, 0.456, 0.406)
CATARACT_NORM_STD = (0.229, 0.224, 0.225)
CATARACT_DEFAULT_THRESHOLD = 0.5

CATARACT_CLASS_LABELS = {
    0: "normale",
    1: "legere",
    2: "moderee",
    3: "severe",
}

CATARACT_MODEL_NAME = "mobilenet_cataract_severity"
CATARACT_MODEL_VERSION = "v1"
