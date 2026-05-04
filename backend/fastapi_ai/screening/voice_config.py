from __future__ import annotations

import os
from pathlib import Path

_SCREENING_DIR = Path(__file__).resolve().parent
_LOCAL_VOICE_MODEL_DIR = _SCREENING_DIR / "models" / "voice"

VOICE_MODEL_DIR = Path(
    os.getenv(
        "VOICE_MODEL_DIR",
        _LOCAL_VOICE_MODEL_DIR.as_posix(),
    )
)
VOICE_SVM_ARTIFACT_PATH = VOICE_MODEL_DIR / "vocadiab_voice_svm_model.joblib"

VOICE_MODEL_NAME = "vocadiab_voice_svm"
VOICE_MODEL_VERSION = "joblib-v1"
VOICE_SAMPLE_RATE = 16000
VOICE_MIN_DURATION_S = 1.5
VOICE_MIN_MEAN_RMS = 0.005
VOICE_MIN_VOICED_RATIO = 0.15
VOICE_MAX_UPLOAD_BYTES = int(os.getenv("VOICE_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
VOICE_SHAP_SEGMENTS = 12

# BYOL-S repository/checkpoint can be copied under screening/models/voice/serab-byols.
# You can override both paths via env vars when needed.
VOICE_BYOLS_REPO = Path(
    os.getenv("VOICE_BYOLS_REPO", (VOICE_MODEL_DIR / "serab-byols").as_posix())
)
VOICE_BYOLS_CHECKPOINT = Path(
    os.getenv(
        "VOICE_BYOLS_CHECKPOINT",
        (
            VOICE_BYOLS_REPO
            / "checkpoints"
            / "cvt_s1-d1-e64_s2-d1-e256_s3-d1-e512_BYOLAs64x96-osandbyolaloss6373-e100-bs256-lr0003-rs42.pth"
        ).as_posix(),
    )
)
