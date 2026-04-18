import os
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parent / "models" / "thermalFoot"
_default_pt = MODEL_DIR / "resnet50_best.pt"
PT_MODEL_PATH = Path(os.environ.get("THERMAL_FOOT_PT_PATH", str(_default_pt)))

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
