from __future__ import annotations

import base64
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from PIL import Image, UnidentifiedImageError
from pytorch_grad_cam import GradCAM
from torchvision import models as tv_models
from torchvision.models import ResNet50_Weights

from screening.config import (
    CLASS_LABELS,
    DEFAULT_THRESHOLD,
    INPUT_SIZE,
    MODEL_NAME,
    MODEL_VERSION,
    NORM_MEAN,
    NORM_STD,
    PT_MODEL_PATH,
)


def _sigmoid(value: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-value))


def _circular_mask_tensor(image_tensor: np.ndarray) -> np.ndarray:
    _, height, width = image_tensor.shape
    y = np.linspace(-1, 1, height, dtype=np.float32)
    x = np.linspace(-1, 1, width, dtype=np.float32)
    grid_y, grid_x = np.meshgrid(y, x, indexing="ij")
    dist = np.sqrt(grid_x**2 + grid_y**2)
    mask = 1.0 - np.clip((dist - 0.85) / 0.1, 0, 1)
    return image_tensor * mask[np.newaxis, :, :]


def _build_model() -> nn.Module:
    model = tv_models.resnet50(weights=ResNet50_Weights.DEFAULT)
    model.fc = nn.Sequential(nn.Dropout(0.4), nn.Linear(2048, 1))
    return model


def _to_base64_jpeg(image_np: np.ndarray) -> str:
    image_uint8 = np.clip(image_np * 255.0, 0, 255).astype(np.uint8)
    image = Image.fromarray(image_uint8)
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


@dataclass
class TongueInferenceResult:
    logit: float
    probability: float
    prediction_index: int
    prediction_label: str
    threshold_used: float
    model_name: str = MODEL_NAME
    model_version: str = MODEL_VERSION


class TonguePtService:
    def __init__(self, model_path: Path = PT_MODEL_PATH, threshold: float = DEFAULT_THRESHOLD):
        self.model_path = model_path
        self.threshold = threshold
        self._model: nn.Module | None = None
        self._grad_cam: GradCAM | None = None

    @property
    def is_loaded(self) -> bool:
        return self._model is not None and self._grad_cam is not None

    def ensure_loaded(self) -> None:
        if self._model is not None and self._grad_cam is not None:
            return
        if not self.model_path.exists():
            raise FileNotFoundError(
                "PyTorch checkpoint not found at "
                f"{self.model_path.as_posix()}."
            )

        model = _build_model()
        state_dict = torch.load(self.model_path, map_location="cpu")
        model.load_state_dict(state_dict)
        model.eval()
        self._model = model
        self._grad_cam = GradCAM(model=model, target_layers=[model.layer4[-1]])

    def preprocess_image_bytes(self, image_bytes: bytes) -> tuple[torch.Tensor, np.ndarray]:
        try:
            image = Image.open(BytesIO(image_bytes)).convert("RGB")
        except UnidentifiedImageError as exc:
            raise ValueError("Uploaded file is not a valid image.") from exc

        image = image.resize((INPUT_SIZE, INPUT_SIZE))
        rgb_np = np.asarray(image, dtype=np.float32) / 255.0
        image_np = rgb_np.copy()
        image_np = np.transpose(image_np, (2, 0, 1))

        mean = np.asarray(NORM_MEAN, dtype=np.float32)[:, np.newaxis, np.newaxis]
        std = np.asarray(NORM_STD, dtype=np.float32)[:, np.newaxis, np.newaxis]
        image_np = (image_np - mean) / std
        image_np = _circular_mask_tensor(image_np)

        batch = np.expand_dims(image_np.astype(np.float32), axis=0)
        return torch.from_numpy(batch), rgb_np

    def predict(self, image_bytes: bytes) -> TongueInferenceResult:
        self.ensure_loaded()
        assert self._model is not None

        input_tensor, _ = self.preprocess_image_bytes(image_bytes)
        with torch.no_grad():
            logits = self._model(input_tensor).detach().cpu().numpy().reshape(-1)

        logit = float(logits[0])
        probability = float(_sigmoid(np.asarray([logit]))[0])
        prediction_idx = 1 if probability >= self.threshold else 0

        return TongueInferenceResult(
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
        with torch.no_grad():
            logits = self._model(input_tensor).detach().cpu().numpy().reshape(-1)

        probability = float(_sigmoid(logits)[0])
        prediction_index = 1 if probability >= self.threshold else 0
        prediction_label = CLASS_LABELS[prediction_index]

        grayscale_cam = self._grad_cam(input_tensor=input_tensor)[0]
        heat = np.clip(grayscale_cam, 0.0, 1.0)

        heat_rgb = np.stack(
            [heat, np.clip(heat * 0.6 + 0.2, 0, 1), np.clip(1.0 - heat, 0, 1)],
            axis=-1,
        )
        overlay = np.clip(rgb_np * 0.55 + heat_rgb * 0.45, 0.0, 1.0)

        return {
            "heatmap_base64": _to_base64_jpeg(overlay),
            "prediction_label": prediction_label,
            "probability": probability,
        }
