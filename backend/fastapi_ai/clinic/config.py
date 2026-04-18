import os
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parent / "models" / "thermalFoot"
# Notebook export uses best_model_resnet50.pt; raw Kaggle training saves resnet50_best.pt.
_CHECKPOINT_CANDIDATES = ("best_model_resnet50.pt", "resnet50_best.pt")


def resolve_pt_model_path() -> Path:
    """Resolve checkpoint path at use time so backend/.env is applied reliably."""
    env = os.environ.get("THERMAL_FOOT_PT_PATH")
    if env:
        return Path(env)
    for name in _CHECKPOINT_CANDIDATES:
        candidate = MODEL_DIR / name
        if candidate.is_file():
            return candidate
    return MODEL_DIR / _CHECKPOINT_CANDIDATES[0]


PT_MODEL_PATH = resolve_pt_model_path()

INPUT_SIZE = 224
NORM_MEAN = (0.485, 0.456, 0.406)
NORM_STD = (0.229, 0.224, 0.225)
DEFAULT_THRESHOLD = 0.5

# ThermoFU training (thermofu-training.ipynb): timm ImageFolder order is typically
# ["DF", "NO DF"] so the DF (diabetes) row of softmax is index 0. Override if your
# checkpoint used a different folder order.
POSITIVE_CLASS_INDEX = int(os.environ.get("THERMAL_FOOT_POSITIVE_IDX", "0"))

TIMM_BACKBONE = "resnet50"
CLASSIFIER_DROPOUT = 0.30

CLASS_LABELS = {
    0: "nondiabetes",
    1: "diabetes",
}

MODEL_NAME = "resnet50_thermal_foot_t2d"
MODEL_VERSION = "pt-v1"
