from __future__ import annotations

import base64
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from threading import Lock

import numpy as np
import timm
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image, UnidentifiedImageError
from pytorch_grad_cam import GradCAM
from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget

from clinic.config import (
    CLASS_LABELS,
    CLASSIFIER_DROPOUT,
    DEFAULT_THRESHOLD,
    INPUT_SIZE,
    MODEL_NAME,
    MODEL_VERSION,
    NORM_MEAN,
    NORM_STD,
    POSITIVE_CLASS_INDEX,
    TIMM_BACKBONE,
    resolve_pt_model_path,
)


def _resolve_checkpoint_state_dict(checkpoint: dict | torch.Tensor) -> dict:
    if not isinstance(checkpoint, dict):
        raise ValueError("Unsupported checkpoint format: expected dict-like state_dict.")
    if "state_dict" in checkpoint and isinstance(checkpoint["state_dict"], dict):
        return checkpoint["state_dict"]
    if "model_state_dict" in checkpoint and isinstance(checkpoint["model_state_dict"], dict):
        return checkpoint["model_state_dict"]
    return checkpoint


def _build_model() -> nn.Module:
    """Match thermofu-training.ipynb: timm ResNet-50, binary softmax head."""
    return timm.create_model(
        TIMM_BACKBONE,
        pretrained=False,
        num_classes=2,
        drop_rate=CLASSIFIER_DROPOUT,
    )


def _normalize_cam_for_display(cam: np.ndarray) -> np.ndarray:
    """Stretch CAM to full [0, 1] per image so low-contrast saliency stays visible."""
    x = np.asarray(cam, dtype=np.float32)
    x = np.maximum(x, 0.0)
    lo, hi = float(x.min()), float(x.max())
    if hi - lo < 1e-6:
        return np.zeros_like(x)
    x = (x - lo) / (hi - lo)
    # Slight gamma: emphasize peaks without crushing mid-tones
    return np.clip(np.power(x, 0.85), 0.0, 1.0)


def _to_base64_jpeg(image_np: np.ndarray) -> str:
    image_uint8 = np.clip(image_np * 255.0, 0, 255).astype(np.uint8)
    image = Image.fromarray(image_uint8)
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


@dataclass
class ThermalFootInferenceResult:
    logit: float  # raw logit for DF class (see POSITIVE_CLASS_INDEX)
    probability: float
    prediction_index: int
    prediction_label: str
    threshold_used: float
    model_name: str = MODEL_NAME
    model_version: str = MODEL_VERSION


class ThermalFootPtService:
    """Binary diabetes risk from foot thermal / infrared images (RGB upload)."""

    def __init__(
        self,
        model_path: Path | None = None,
        threshold: float = DEFAULT_THRESHOLD,
    ):
        self._model_path_override = model_path
        self.threshold = threshold
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._model: nn.Module | None = None
        self._grad_cam: GradCAM | None = None
        self._load_lock = Lock()
        # GradCAM + autograd are not thread-safe; parallel requests corrupt hooks / backward.
        self._inference_lock = Lock()

    @property
    def model_path(self) -> Path:
        if self._model_path_override is not None:
            return self._model_path_override
        return resolve_pt_model_path()

    @property
    def is_loaded(self) -> bool:
        return self._model is not None and self._grad_cam is not None

    def ensure_loaded(self) -> None:
        if self._model is not None and self._grad_cam is not None:
            return
        with self._load_lock:
            if self._model is not None and self._grad_cam is not None:
                return
            if not self.model_path.exists():
                raise FileNotFoundError(
                    "PyTorch checkpoint not found at "
                    f"{self.model_path.as_posix()}. "
                    "Add best_model_resnet50.pt (ThermoFU export) or resnet50_best.pt "
                    "(training checkpoints) under clinic/models/thermalFoot/, or set "
                    "THERMAL_FOOT_PT_PATH to your .pt file."
                )

            model = _build_model().to(self.device)
            checkpoint = torch.load(self.model_path, map_location=self.device)
            state_dict = _resolve_checkpoint_state_dict(checkpoint)
            model.load_state_dict(state_dict, strict=True)
            model.eval()
            self._model = model
            self._grad_cam = GradCAM(
                model=model,
                target_layers=[model.layer4[-1]],
            )

    def preprocess_image_bytes(self, image_bytes: bytes) -> tuple[torch.Tensor, np.ndarray]:
        try:
            image = Image.open(BytesIO(image_bytes)).convert("RGB")
        except UnidentifiedImageError as exc:
            raise ValueError("Uploaded file is not a valid image.") from exc

        image = image.resize((INPUT_SIZE, INPUT_SIZE), Image.Resampling.BICUBIC)
        rgb_np = np.asarray(image, dtype=np.float32) / 255.0
        image_chw = np.transpose(rgb_np.copy(), (2, 0, 1))

        mean = np.asarray(NORM_MEAN, dtype=np.float32)[:, np.newaxis, np.newaxis]
        std = np.asarray(NORM_STD, dtype=np.float32)[:, np.newaxis, np.newaxis]
        image_chw = (image_chw - mean) / std

        batch = np.expand_dims(image_chw.astype(np.float32), axis=0)
        input_tensor = torch.from_numpy(batch).to(self.device)
        return input_tensor, rgb_np

    def predict(self, image_bytes: bytes) -> ThermalFootInferenceResult:
        self.ensure_loaded()
        assert self._model is not None

        input_tensor, _ = self.preprocess_image_bytes(image_bytes)
        with self._inference_lock:
            with torch.inference_mode():
                logits = self._model(input_tensor).detach().cpu().numpy().reshape(-1)

        logit = float(logits[POSITIVE_CLASS_INDEX])
        probs = F.softmax(torch.from_numpy(logits), dim=0).numpy()
        probability = float(probs[POSITIVE_CLASS_INDEX])
        prediction_idx = 1 if probability >= self.threshold else 0

        return ThermalFootInferenceResult(
            logit=logit,
            probability=probability,
            prediction_index=prediction_idx,
            prediction_label=CLASS_LABELS[prediction_idx],
            threshold_used=self.threshold,
        )

    def generate_gradcam(self, image_bytes: bytes) -> dict:
        self.ensure_loaded()
        assert self._model is not None
        assert self._grad_cam is not None

        input_tensor, rgb_np = self.preprocess_image_bytes(image_bytes)
        with self._inference_lock:
            with torch.inference_mode():
                logits = self._model(input_tensor).detach().cpu().numpy().reshape(-1)

            probs = F.softmax(torch.from_numpy(logits), dim=0).numpy()
            probability = float(probs[POSITIVE_CLASS_INDEX])
            prediction_index = 1 if probability >= self.threshold else 0
            prediction_label = CLASS_LABELS[prediction_index]

            grayscale_cam = self._grad_cam(
                input_tensor=input_tensor,
                targets=[ClassifierOutputTarget(POSITIVE_CLASS_INDEX)],
            )[0]

        heat = _normalize_cam_for_display(grayscale_cam)

        heat_rgb = np.stack(
            [heat, np.clip(heat * 0.55 + 0.15, 0, 1), np.clip(1.0 - heat * 0.95, 0, 1)],
            axis=-1,
        )
        # Weight heatmap more than base so attribution is easy to see on thermal palettes
        overlay = np.clip(rgb_np * 0.38 + heat_rgb * 0.62, 0.0, 1.0)

        return {
            "heatmap_base64": _to_base64_jpeg(overlay),
            "prediction_label": prediction_label,
            "probability": probability,
        }
