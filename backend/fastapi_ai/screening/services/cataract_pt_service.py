from __future__ import annotations

import base64
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from threading import Lock

import numpy as np
import torch
import torch.nn as nn
from PIL import Image, UnidentifiedImageError
from pytorch_grad_cam import GradCAM
from torchvision import models as tv_models

from screening.config import (
    CATARACT_CLASS_LABELS,
    CATARACT_DEFAULT_THRESHOLD,
    CATARACT_INPUT_SIZE,
    CATARACT_MODEL_NAME,
    CATARACT_MODEL_VERSION,
    CATARACT_NORM_MEAN,
    CATARACT_NORM_STD,
    CATARACT_PT_MODEL_PATH,
)


def _softmax(values: np.ndarray) -> np.ndarray:
    """Compute softmax probabilities."""
    e_x = np.exp(values - np.max(values, axis=-1, keepdims=True))
    return e_x / e_x.sum(axis=-1, keepdims=True)


def _resolve_checkpoint_state_dict(checkpoint: dict | torch.Tensor) -> dict:
    """Extract state dict from checkpoint with metadata."""
    if not isinstance(checkpoint, dict):
        raise ValueError("Unsupported checkpoint format: expected dict-like state_dict.")
    if "model_state_dict" in checkpoint and isinstance(checkpoint["model_state_dict"], dict):
        return checkpoint["model_state_dict"]
    if "state_dict" in checkpoint and isinstance(checkpoint["state_dict"], dict):
        return checkpoint["state_dict"]
    return checkpoint


def _to_base64_jpeg(image_np: np.ndarray) -> str:
    """Convert numpy array to base64 JPEG string."""
    image_uint8 = np.clip(image_np * 255.0, 0, 255).astype(np.uint8)
    image = Image.fromarray(image_uint8)
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def _build_model() -> nn.Module:
    """Build the exact MobileNetV3-Large architecture used by the checkpoint."""
    model = tv_models.mobilenet_v3_large(weights=None)
    n_features = model.classifier[0].in_features
    model.classifier = nn.Sequential(
        nn.Linear(n_features, 256),
        nn.Hardswish(),
        nn.Dropout(0.3),
        nn.Linear(256, 4),
    )
    return model


def _build_legacy_timm_model() -> nn.Module:
    """Fallback for older experimental checkpoints saved with timm MobileNetV3-Small."""
    import timm

    model = timm.create_model("mobilenetv3_small_100", pretrained=False, num_classes=0)
    n_features = model.num_features
    model.classifier = nn.Sequential(
        nn.BatchNorm1d(n_features),
        nn.Dropout(0.3),
        nn.Linear(n_features, 256),
        nn.GELU(),
        nn.Dropout(0.2),
        nn.Linear(256, 4),
    )
    return model


@dataclass
class CataractInferenceResult:
    prediction_index: int  # 0-3
    prediction_label: str
    confidence: float
    p_cataract: float
    probabilities: dict  # {class_name: probability}
    model_name: str = CATARACT_MODEL_NAME
    model_version: str = CATARACT_MODEL_VERSION


class CataractPtService:
    """Service for cataract severity classification using MobileNet PyTorch model."""

    def __init__(self, model_path: Path = CATARACT_PT_MODEL_PATH, threshold: float = CATARACT_DEFAULT_THRESHOLD):
        self.model_path = model_path
        self.threshold = threshold
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._model: nn.Module | None = None
        self._grad_cam: GradCAM | None = None
        self._load_lock = Lock()

    @property
    def is_loaded(self) -> bool:
        return self._model is not None and self._grad_cam is not None

    def ensure_loaded(self) -> None:
        """Load model if not already loaded (thread-safe)."""
        if self._model is not None and self._grad_cam is not None:
            return
        with self._load_lock:
            if self._model is not None and self._grad_cam is not None:
                return
            if not self.model_path.exists():
                raise FileNotFoundError(
                    f"PyTorch checkpoint not found at {self.model_path.as_posix()}."
                )

            checkpoint = torch.load(self.model_path, map_location=self.device, weights_only=False)
            state_dict = _resolve_checkpoint_state_dict(checkpoint)
            model = _build_model().to(self.device)
            try:
                model.load_state_dict(state_dict, strict=True)
            except RuntimeError:
                model = _build_legacy_timm_model().to(self.device)
                model.load_state_dict(state_dict, strict=False)
            model.eval()
            self._model = model
            
            # Setup Grad-CAM on the last layer of MobileNet
            self._grad_cam = GradCAM(model=model, target_layers=[model.features[-1]])

    def preprocess_image_bytes(self, image_bytes: bytes) -> tuple[torch.Tensor, np.ndarray]:
        """Preprocess image bytes: resize, normalize, return tensor and RGB array."""
        try:
            image = Image.open(BytesIO(image_bytes)).convert("RGB")
        except UnidentifiedImageError as exc:
            raise ValueError("Uploaded file is not a valid image.") from exc

        # Resize to model input size
        image = image.resize((CATARACT_INPUT_SIZE, CATARACT_INPUT_SIZE), Image.Resampling.BICUBIC)
        rgb_np = np.asarray(image, dtype=np.float32) / 255.0
        
        # Convert to CHW format
        image_chw = np.transpose(rgb_np.copy(), (2, 0, 1))

        # Normalize with ImageNet stats
        mean = np.asarray(CATARACT_NORM_MEAN, dtype=np.float32)[:, np.newaxis, np.newaxis]
        std = np.asarray(CATARACT_NORM_STD, dtype=np.float32)[:, np.newaxis, np.newaxis]
        image_chw = (image_chw - mean) / std

        # Create batch
        batch = np.expand_dims(image_chw.astype(np.float32), axis=0)
        input_tensor = torch.from_numpy(batch).to(self.device)
        return input_tensor, rgb_np

    def predict(self, image_bytes: bytes) -> CataractInferenceResult:
        """Predict cataract severity from image bytes."""
        self.ensure_loaded()
        assert self._model is not None

        input_tensor, _ = self.preprocess_image_bytes(image_bytes)
        
        with torch.inference_mode():
            logits = self._model(input_tensor).detach().cpu().numpy().reshape(-1)

        # Compute softmax probabilities
        probs = _softmax(logits)
        prediction_idx = int(np.argmax(probs))
        prediction_label = CATARACT_CLASS_LABELS[prediction_idx]
        confidence = float(probs[prediction_idx])
        p_cataract = float(np.sum(probs[1:]))

        # Build probabilities dict
        probabilities = {
            CATARACT_CLASS_LABELS[i]: float(probs[i]) for i in range(len(CATARACT_CLASS_LABELS))
        }

        return CataractInferenceResult(
            prediction_index=prediction_idx,
            prediction_label=prediction_label,
            confidence=confidence,
            p_cataract=p_cataract,
            probabilities=probabilities,
        )

    def generate_gradcam(self, image_bytes: bytes) -> dict:
        """Generate Grad-CAM heatmap for prediction visualization."""
        self.ensure_loaded()
        assert self._model is not None
        assert self._grad_cam is not None

        input_tensor, rgb_np = self.preprocess_image_bytes(image_bytes)
        
        with torch.inference_mode():
            logits = self._model(input_tensor).detach().cpu().numpy().reshape(-1)

        probs = _softmax(logits)
        prediction_idx = int(np.argmax(probs))
        prediction_label = CATARACT_CLASS_LABELS[prediction_idx]
        confidence = float(probs[prediction_idx])
        p_cataract = float(np.sum(probs[1:]))

        # Generate Grad-CAM
        grayscale_cam = self._grad_cam(input_tensor=input_tensor)[0]
        heat = np.clip(grayscale_cam, 0.0, 1.0)

        # Create heatmap overlay (jet colormap-like)
        heat_rgb = np.stack(
            [heat, np.clip(heat * 0.6 + 0.2, 0, 1), np.clip(1.0 - heat, 0, 1)],
            axis=-1,
        )
        overlay = np.clip(rgb_np * 0.55 + heat_rgb * 0.45, 0.0, 1.0)

        probabilities = {
            CATARACT_CLASS_LABELS[i]: float(probs[i]) for i in range(len(CATARACT_CLASS_LABELS))
        }

        return {
            "heatmap_base64": _to_base64_jpeg(overlay),
            "prediction_label": prediction_label,
            "confidence": confidence,
            "p_cataract": p_cataract,
            "probabilities": probabilities,
        }
