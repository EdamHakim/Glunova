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

# Weights stay under clinic/models/DFUSegmentation/; only this module file lives in clinic/.
DEFAULT_CHECKPOINT_PATH = (
    Path(__file__).resolve().parent / "models" / "DFUSegmentation" / "resnet34_unet_weights.pth"
)

# Rough anatomical prior for mm/pixel when no ruler is present: assume ~24 cm aligns with longest side.
DEFAULT_ASSUMED_FOOT_SPAN_MM = 240.0


def estimate_mm_per_pixel_assumed_foot_span(
    image_bytes: bytes,
    *,
    assumed_span_mm: float = DEFAULT_ASSUMED_FOOT_SPAN_MM,
    lo: float = 0.015,
    hi: float = 12.0,
) -> float:
    """Very approximate scale: assumes the foot spans the image's longest edge."""
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    w, h = image.size
    long_px = float(max(w, h))
    if long_px < 16:
        raise ValueError("Image dimensions are too small for mm/pixel estimation.")
    mm_px = float(assumed_span_mm / long_px)
    return float(max(lo, min(hi, mm_px)))


def _auto_seg_threshold(probs: np.ndarray) -> float:
    """Pick a binary threshold by scanning downward from the map maximum (per-image heuristic)."""
    pmax = float(probs.max())
    if pmax < 0.24:
        return 0.5
    min_ar = max(5.0 / float(probs.size), 1.2e-5)
    max_ar = 0.32
    for t in np.arange(min(0.94, pmax + 1e-6), 0.16, -0.0125):
        ar = float((probs >= t).mean())
        if min_ar <= ar <= max_ar:
            return float(round(float(t), 5))
    return 0.5


class _DoubleConv(nn.Module):
    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.block(x)


class _Down(nn.Module):
    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.pool_conv = nn.Sequential(
            nn.MaxPool2d(kernel_size=2, stride=2),
            _DoubleConv(in_channels, out_channels),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.pool_conv(x)


class _Up(nn.Module):
    def __init__(self, in_channels: int, skip_channels: int, out_channels: int):
        super().__init__()
        self.up = nn.ConvTranspose2d(in_channels, in_channels // 2, kernel_size=2, stride=2)
        self.conv = _DoubleConv((in_channels // 2) + skip_channels, out_channels)

    def forward(self, x: torch.Tensor, skip: torch.Tensor) -> torch.Tensor:
        x = self.up(x)
        diff_y = skip.size(2) - x.size(2)
        diff_x = skip.size(3) - x.size(3)
        if diff_y != 0 or diff_x != 0:
            x = nn.functional.pad(
                x,
                [diff_x // 2, diff_x - diff_x // 2, diff_y // 2, diff_y - diff_y // 2],
            )
        x = torch.cat([skip, x], dim=1)
        return self.conv(x)


class DFUSegmentation(nn.Module):
    """
    Lightweight U-Net style segmenter for diabetic foot ulcer masks.

    Input:  B x 3 x H x W
    Output: B x 1 x H x W (logits)
    """

    def __init__(self, in_channels: int = 3, base_channels: int = 32):
        super().__init__()
        self.inc = _DoubleConv(in_channels, base_channels)
        self.down1 = _Down(base_channels, base_channels * 2)
        self.down2 = _Down(base_channels * 2, base_channels * 4)
        self.down3 = _Down(base_channels * 4, base_channels * 8)
        self.bottleneck = _Down(base_channels * 8, base_channels * 16)

        self.up1 = _Up(base_channels * 16, base_channels * 8, base_channels * 8)
        self.up2 = _Up(base_channels * 8, base_channels * 4, base_channels * 4)
        self.up3 = _Up(base_channels * 4, base_channels * 2, base_channels * 2)
        self.up4 = _Up(base_channels * 2, base_channels, base_channels)

        self.outc = nn.Conv2d(base_channels, 1, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x1 = self.inc(x)
        x2 = self.down1(x1)
        x3 = self.down2(x2)
        x4 = self.down3(x3)
        x5 = self.bottleneck(x4)

        x = self.up1(x5, x4)
        x = self.up2(x, x3)
        x = self.up3(x, x2)
        x = self.up4(x, x1)
        return self.outc(x)


@dataclass
class DFUSegmentationResult:
    ulcer_detected: bool
    ulcer_area_ratio: float
    ulcer_area_px: int
    bbox_x: int
    bbox_y: int
    bbox_width_px: int
    bbox_height_px: int
    mask_base64: str
    overlay_base64: str
    threshold_used: float


class DFUSegmenter:
    """
    Inference wrapper for DFUSegmentation checkpoints.
    """

    def __init__(
        self,
        checkpoint_path: Path | None = None,
        input_size: int = 256,
        mean: tuple[float, float, float] = (0.485, 0.456, 0.406),
        std: tuple[float, float, float] = (0.229, 0.224, 0.225),
    ):
        self.checkpoint_path = checkpoint_path or DEFAULT_CHECKPOINT_PATH
        self.input_size = input_size
        self.mean = np.array(mean, dtype=np.float32)[:, None, None]
        self.std = np.array(std, dtype=np.float32)[:, None, None]
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._model: nn.Module | None = None
        self._load_lock = Lock()

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def _resolve_state_dict(self, checkpoint: dict) -> dict:
        if "state_dict" in checkpoint and isinstance(checkpoint["state_dict"], dict):
            return checkpoint["state_dict"]
        if "model_state_dict" in checkpoint and isinstance(checkpoint["model_state_dict"], dict):
            return checkpoint["model_state_dict"]
        return checkpoint

    def _is_smp_unet_state_dict(self, state_dict: dict) -> bool:
        # segmentation_models_pytorch Unet checkpoints usually expose these key prefixes.
        keys = list(state_dict.keys())
        return any(k.startswith("encoder.") for k in keys) and any(
            k.startswith("decoder.") or k.startswith("segmentation_head.") for k in keys
        )

    def _build_smp_resnet34_unet(self) -> nn.Module:
        try:
            import segmentation_models_pytorch as smp  # type: ignore
        except Exception as exc:
            raise RuntimeError(
                "Checkpoint appears to be segmentation_models_pytorch Unet(resnet34), "
                "but 'segmentation_models_pytorch' is not installed."
            ) from exc
        return smp.Unet(
            encoder_name="resnet34",
            encoder_weights=None,
            in_channels=3,
            classes=1,
        )

    def ensure_loaded(self) -> None:
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:
                return
            if not self.checkpoint_path.exists():
                raise FileNotFoundError(
                    "DFU segmentation checkpoint not found at "
                    f"{self.checkpoint_path.as_posix()}."
                )
            checkpoint = torch.load(self.checkpoint_path, map_location=self.device)
            if not isinstance(checkpoint, dict):
                raise ValueError("Unsupported checkpoint format for DFUSegmentation.")

            state_dict = self._resolve_state_dict(checkpoint)
            if not isinstance(state_dict, dict):
                raise ValueError("Checkpoint state_dict format is invalid for DFU segmentation.")

            # Pick architecture from checkpoint signature to avoid loading wrong module type.
            if self._is_smp_unet_state_dict(state_dict):
                model = self._build_smp_resnet34_unet().to(self.device)
            else:
                model = DFUSegmentation().to(self.device)

            model.load_state_dict(state_dict, strict=True)
            model.eval()
            self._model = model

    def _encode_png(self, image_np: np.ndarray) -> str:
        image_uint8 = np.clip(image_np * 255.0, 0, 255).astype(np.uint8)
        image = Image.fromarray(image_uint8)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def _preprocess(self, image_bytes: bytes) -> tuple[torch.Tensor, np.ndarray]:
        try:
            image = Image.open(BytesIO(image_bytes)).convert("RGB")
        except UnidentifiedImageError as exc:
            raise ValueError("Uploaded file is not a valid image.") from exc

        image = image.resize((self.input_size, self.input_size), Image.Resampling.BILINEAR)
        rgb = np.asarray(image, dtype=np.float32) / 255.0
        chw = np.transpose(rgb, (2, 0, 1))
        chw = (chw - self.mean) / self.std
        batch = np.expand_dims(chw.astype(np.float32), axis=0)
        return torch.from_numpy(batch).to(self.device), rgb

    def predict(self, image_bytes: bytes, threshold: float | None = 0.5) -> DFUSegmentationResult:
        if threshold is not None and (threshold < 0 or threshold > 1):
            raise ValueError("threshold must be in [0, 1].")

        self.ensure_loaded()
        assert self._model is not None

        inputs, rgb = self._preprocess(image_bytes)
        with torch.inference_mode():
            logits = self._model(inputs)
            probs = torch.sigmoid(logits).cpu().numpy()[0, 0]

        thresh_used = _auto_seg_threshold(probs) if threshold is None else float(threshold)
        mask = (probs >= thresh_used).astype(np.float32)
        area_px = int(mask.sum())
        area_ratio = float(mask.mean())
        ulcer_detected = bool(area_ratio > 0)
        if ulcer_detected:
            ys, xs = np.where(mask > 0)
            x_min = int(xs.min())
            x_max = int(xs.max())
            y_min = int(ys.min())
            y_max = int(ys.max())
            bbox_width = (x_max - x_min) + 1
            bbox_height = (y_max - y_min) + 1
        else:
            x_min = 0
            y_min = 0
            bbox_width = 0
            bbox_height = 0

        mask_rgb = np.stack([mask, mask, mask], axis=-1)
        overlay = np.clip(rgb * 0.65 + np.stack([mask, np.zeros_like(mask), np.zeros_like(mask)], axis=-1) * 0.35, 0.0, 1.0)

        return DFUSegmentationResult(
            ulcer_detected=ulcer_detected,
            ulcer_area_ratio=area_ratio,
            ulcer_area_px=area_px,
            bbox_x=x_min,
            bbox_y=y_min,
            bbox_width_px=bbox_width,
            bbox_height_px=bbox_height,
            mask_base64=self._encode_png(mask_rgb),
            overlay_base64=self._encode_png(overlay),
            threshold_used=thresh_used,
        )
