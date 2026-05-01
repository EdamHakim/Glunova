from __future__ import annotations

import base64
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from threading import Lock

import cv2
import numpy as np
import timm
import torch
import torch.nn as nn
from PIL import Image
from pytorch_grad_cam import EigenCAM, HiResCAM
from pytorch_grad_cam.utils.image import show_cam_on_image
from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget
from scipy.ndimage import gaussian_filter

from clinic.config_retinopathy import (
    CLINICAL_GRADE_LABELS,
    V8_BACKBONE,
    V8_GRADE_NAMES,
    V8_IN_CHANS,
    V8_INPUT_SIZE,
    V8_MODEL_NAME,
    V8_MODEL_VERSION,
    V8_NORM_MEAN,
    V8_NORM_STD,
    V8_NUM_CLASSES,
    V51_BACKBONE,
    V51_CLASS_NAMES,
    V51_DEFAULT_THRESHOLD,
    V51_IN_CHANS,
    V51_INPUT_SIZE,
    V51_MODEL_NAME,
    V51_MODEL_VERSION,
    V51_NORM_MEAN,
    V51_NORM_STD,
    V51_NUM_CLASSES,
    resolve_v51_pt_path,
    resolve_v8_pt_path,
)


# ═══════════════════════════════════════════════════════════════════
# Shared preprocessing — verbatim from glunova_*_inference.py
# ═══════════════════════════════════════════════════════════════════

def _decode_image_bytes(image_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image")
    return img


def _circular_crop_and_pad(img_bgr: np.ndarray, size: int) -> np.ndarray:
    """Detect retinal disc, mask, crop to bbox, resize, black-pad to size×size. Returns RGB uint8."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, th = cv2.threshold(blur, 15, 255, cv2.THRESH_BINARY)
    cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if cnts:
        c = max(cnts, key=cv2.contourArea)
        (cx, cy), r = cv2.minEnclosingCircle(c)
        cx, cy, r = int(cx), int(cy), int(r)
        mask = np.zeros(gray.shape, dtype=np.uint8)
        cv2.circle(mask, (cx, cy), int(r * 0.97), 255, -1)
        img_bgr = cv2.bitwise_and(img_bgr, img_bgr, mask=mask)
        x1, y1 = max(0, cx - r), max(0, cy - r)
        x2, y2 = min(img_bgr.shape[1], cx + r), min(img_bgr.shape[0], cy + r)
        img_bgr = img_bgr[y1:y2, x1:x2]

    h, w = img_bgr.shape[:2]
    if h == 0 or w == 0:
        return np.zeros((size, size, 3), dtype=np.uint8)
    scale = size / max(h, w)
    nh, nw = int(h * scale), int(w * scale)
    img_bgr = cv2.resize(img_bgr, (nw, nh), interpolation=cv2.INTER_AREA)
    ph, pw = size - nh, size - nw
    top, left = ph // 2, pw // 2
    img_bgr = cv2.copyMakeBorder(
        img_bgr, top, ph - top, left, pw - left,
        cv2.BORDER_CONSTANT, value=[0, 0, 0],
    )
    return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)


def _retina_mask(img_uint8: np.ndarray, kernel_size: int = 15, blur_size: int = 21) -> np.ndarray:
    gray = cv2.cvtColor(img_uint8, cv2.COLOR_RGB2GRAY) if img_uint8.ndim == 3 else img_uint8
    mask = (gray > 8).astype(np.float32)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
    mask = cv2.erode(mask, kernel, iterations=2)
    mask = cv2.GaussianBlur(mask, (blur_size, blur_size), 0)
    return mask


def _resolve_state_dict(checkpoint) -> dict:
    if not isinstance(checkpoint, dict):
        raise ValueError("Unsupported checkpoint format: expected dict-like state_dict.")
    for key in ("model_state_dict", "state_dict"):
        if key in checkpoint and isinstance(checkpoint[key], dict):
            return checkpoint[key]
    return checkpoint


def _to_base64_jpeg(image_uint8: np.ndarray) -> str:
    image = Image.fromarray(image_uint8)
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def _tta_8_softmax(model: nn.Module, tensor: torch.Tensor) -> np.ndarray:
    """8-orientation TTA average (rotations + flips)."""
    tfs = (
        lambda x: x,
        lambda x: torch.flip(x, [3]),
        lambda x: torch.flip(x, [2]),
        lambda x: torch.flip(x, [2, 3]),
        lambda x: torch.rot90(x, 1, [2, 3]),
        lambda x: torch.rot90(x, 2, [2, 3]),
        lambda x: torch.rot90(x, 3, [2, 3]),
        lambda x: torch.flip(torch.rot90(x, 1, [2, 3]), [3]),
    )
    probs = [torch.softmax(model(f(tensor)), dim=1) for f in tfs]
    return torch.stack(probs).mean(0)[0].cpu().float().numpy()


# ═══════════════════════════════════════════════════════════════════
# V5.1 binary — EfficientNetV2-S, 512×512 RGB
# ═══════════════════════════════════════════════════════════════════

def _make_tensor_v51(img_rgb: np.ndarray, device: torch.device) -> torch.Tensor:
    arr = img_rgb.astype(np.float32) / 255.0
    mean = np.asarray(V51_NORM_MEAN, dtype=np.float32)
    std = np.asarray(V51_NORM_STD, dtype=np.float32)
    arr = (arr - mean) / std
    tensor = torch.from_numpy(arr.transpose(2, 0, 1)).float().unsqueeze(0)
    return tensor.to(device)


@dataclass
class DRBinaryResult:
    dr_detected: bool
    dr_probability: float
    no_dr_probability: float
    threshold_used: float
    confidence: float
    model_name: str = V51_MODEL_NAME
    model_version: str = V51_MODEL_VERSION


class DRBinaryService:
    """Glunova V5.1 — fundus binary classifier (No DR vs DR) with TTA + EigenCAM."""

    def __init__(
        self,
        model_path: Path | None = None,
        threshold: float = V51_DEFAULT_THRESHOLD,
        use_tta: bool = True,
    ):
        self._model_path_override = model_path
        self.threshold = threshold
        self.use_tta = use_tta
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._model: nn.Module | None = None
        self._cam: EigenCAM | None = None
        self._load_lock = Lock()
        # GradCAM + autograd are not thread-safe; serialize per-process.
        self._inference_lock = Lock()

    @property
    def model_path(self) -> Path:
        if self._model_path_override is not None:
            return self._model_path_override
        return resolve_v51_pt_path()

    @property
    def is_loaded(self) -> bool:
        return self._model is not None and self._cam is not None

    def ensure_loaded(self) -> None:
        if self._model is not None and self._cam is not None:
            return
        with self._load_lock:
            if self._model is not None and self._cam is not None:
                return
            path = self.model_path
            if not path.exists():
                raise FileNotFoundError(
                    f"DR V5.1 checkpoint not found at {path.as_posix()}. "
                    "Place best_v5_1.pt under clinic/models/retinopathy/, "
                    "or set DR_V51_PT_PATH."
                )
            model = timm.create_model(
                V51_BACKBONE,
                pretrained=False,
                num_classes=V51_NUM_CLASSES,
                in_chans=V51_IN_CHANS,
            ).to(self.device)
            ckpt = torch.load(path, map_location=self.device, weights_only=False)
            model.load_state_dict(_resolve_state_dict(ckpt))
            model.eval()
            self._model = model
            self._cam = EigenCAM(model=model, target_layers=[model.blocks[-1]])

    def predict(self, image_bytes: bytes) -> DRBinaryResult:
        self.ensure_loaded()
        assert self._model is not None
        bgr = _decode_image_bytes(image_bytes)
        img_rgb = _circular_crop_and_pad(bgr, V51_INPUT_SIZE)
        tensor = _make_tensor_v51(img_rgb, self.device)
        with self._inference_lock:
            with torch.inference_mode():
                if self.use_tta:
                    probs = _tta_8_softmax(self._model, tensor)
                else:
                    probs = torch.softmax(self._model(tensor), dim=1)[0].cpu().float().numpy()
        p_no_dr = float(probs[0])
        p_dr = float(probs[1])
        return DRBinaryResult(
            dr_detected=p_dr >= self.threshold,
            dr_probability=p_dr,
            no_dr_probability=p_no_dr,
            threshold_used=self.threshold,
            confidence=float(max(p_no_dr, p_dr)),
        )

    def generate_eigencam(self, image_bytes: bytes) -> dict:
        self.ensure_loaded()
        assert self._model is not None
        assert self._cam is not None
        bgr = _decode_image_bytes(image_bytes)
        img_rgb = _circular_crop_and_pad(bgr, V51_INPUT_SIZE)
        rgb01 = img_rgb.astype(np.float32) / 255.0
        tensor = _make_tensor_v51(img_rgb, self.device)
        with self._inference_lock:
            with torch.inference_mode():
                probs = torch.softmax(self._model(tensor), dim=1)[0].cpu().float().numpy()
            cam = self._cam(input_tensor=tensor, targets=[ClassifierOutputTarget(1)])[0]
        retina = _retina_mask(img_rgb, kernel_size=15, blur_size=21)
        cam = cam * retina
        if cam.max() > 0:
            cam = cam / cam.max()
        overlay = show_cam_on_image(rgb01, cam, use_rgb=True)
        attn_area = float((cam > 0.3).sum() / max((retina > 0.5).sum(), 1))
        return {
            "heatmap_base64": _to_base64_jpeg(overlay),
            "dr_probability": float(probs[1]),
            "attention_area": attn_area,
            "class_names": list(V51_CLASS_NAMES),
        }


# ═══════════════════════════════════════════════════════════════════
# V8 severity — ConvNeXt-Base + TriplePool, 728×728 RGBG
# ═══════════════════════════════════════════════════════════════════

class TriplePoolModel(nn.Module):
    """ConvNeXt-Base with Triple Pooling head (Avg + Max + Quadrant 2x2 -> Linear)."""

    def __init__(self, num_classes: int = 4, in_chans: int = 4, drop_rate: float = 0.3, drop_path_rate: float = 0.3):
        super().__init__()
        self.backbone = timm.create_model(
            V8_BACKBONE,
            pretrained=False,
            in_chans=in_chans,
            num_classes=0,
            drop_path_rate=drop_path_rate,
        )
        feat_dim = self.backbone.num_features  # 1024 for ConvNeXt-Base
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.max_pool = nn.AdaptiveMaxPool2d(1)
        self.quad_pool = nn.AdaptiveAvgPool2d(2)
        self.drop = nn.Dropout(drop_rate)
        # 6144 = 1024 (avg) + 1024 (max) + 4096 (quad 2x2 flattened)
        self.head = nn.Linear(feat_dim * 6, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        feats = self.backbone.forward_features(x)
        avg_p = self.avg_pool(feats).flatten(1)
        max_p = self.max_pool(feats).flatten(1)
        quad_p = self.quad_pool(feats).flatten(1)
        pooled = torch.cat([avg_p, max_p, quad_p], dim=1)
        return self.head(self.drop(pooled))


def _extract_green_enhanced(img_rgb: np.ndarray) -> np.ndarray:
    green = img_rgb[:, :, 1]
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    return clahe.apply(green)


def _make_tensor_v8(img_rgb: np.ndarray, device: torch.device) -> torch.Tensor:
    green = _extract_green_enhanced(img_rgb)
    rgb_n = (img_rgb.astype(np.float32) / 255.0 - np.array(V8_NORM_MEAN[:3])) / np.array(V8_NORM_STD[:3])
    g_n = (green.astype(np.float32) / 255.0 - V8_NORM_MEAN[3]) / V8_NORM_STD[3]
    arr = np.concatenate([rgb_n, g_n[..., None]], axis=-1)
    tensor = torch.from_numpy(arr.transpose(2, 0, 1)).float().unsqueeze(0)
    return tensor.to(device)


def _percentile_norm(x: np.ndarray, p_low: float = 30.0, p_high: float = 99.5) -> np.ndarray:
    pos = x[x > 0]
    if pos.size == 0:
        return np.clip(x, 0, None)
    lo = np.percentile(pos, p_low)
    hi = np.percentile(x, p_high)
    if hi <= lo:
        return np.clip(x - lo, 0, None)
    return np.clip((x - lo) / (hi - lo), 0, 1)


@dataclass
class DRSeverityResult:
    grade_idx: int  # 0..3 (Mild..Proliferative)
    grade_label: str
    confidence: float
    probabilities: dict
    model_name: str = V8_MODEL_NAME
    model_version: str = V8_MODEL_VERSION


class DRSeverityService:
    """Glunova V8 — fundus 4-class severity with TTA + Multi-Scale HiResCAM."""

    def __init__(self, model_path: Path | None = None, use_tta: bool = True):
        self._model_path_override = model_path
        self.use_tta = use_tta
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._model: TriplePoolModel | None = None
        self._cams: dict[str, HiResCAM] | None = None
        self._load_lock = Lock()
        self._inference_lock = Lock()

    @property
    def model_path(self) -> Path:
        if self._model_path_override is not None:
            return self._model_path_override
        return resolve_v8_pt_path()

    @property
    def is_loaded(self) -> bool:
        return self._model is not None and self._cams is not None

    def ensure_loaded(self) -> None:
        if self._model is not None and self._cams is not None:
            return
        with self._load_lock:
            if self._model is not None and self._cams is not None:
                return
            path = self.model_path
            if not path.exists():
                raise FileNotFoundError(
                    f"DR V8 checkpoint not found at {path.as_posix()}. "
                    "Place best_v8.pt under clinic/models/retinopathy/, "
                    "or set DR_V8_PT_PATH."
                )
            model = TriplePoolModel(num_classes=V8_NUM_CLASSES, in_chans=V8_IN_CHANS).to(self.device)
            ckpt = torch.load(path, map_location=self.device, weights_only=False)
            model.load_state_dict(_resolve_state_dict(ckpt))
            model.eval()
            self._model = model
            self._cams = {
                "deep": HiResCAM(model=model, target_layers=[model.backbone.stages[-1]]),
                "mid": HiResCAM(model=model, target_layers=[model.backbone.stages[-2]]),
                "shallow": HiResCAM(model=model, target_layers=[model.backbone.stages[-3]]),
            }

    def predict(self, image_bytes: bytes) -> DRSeverityResult:
        self.ensure_loaded()
        assert self._model is not None
        bgr = _decode_image_bytes(image_bytes)
        img_rgb = _circular_crop_and_pad(bgr, V8_INPUT_SIZE)
        tensor = _make_tensor_v8(img_rgb, self.device)
        with self._inference_lock:
            with torch.inference_mode():
                if self.use_tta:
                    probs = _tta_8_softmax(self._model, tensor)
                else:
                    probs = torch.softmax(self._model(tensor), dim=1)[0].cpu().float().numpy()
        pred = int(np.argmax(probs))
        return DRSeverityResult(
            grade_idx=pred,
            grade_label=V8_GRADE_NAMES[pred],
            confidence=float(probs[pred]),
            probabilities={V8_GRADE_NAMES[i]: float(probs[i]) for i in range(V8_NUM_CLASSES)},
        )

    def generate_hires_cam(self, image_bytes: bytes, target_class: int | None = None) -> dict:
        self.ensure_loaded()
        assert self._model is not None
        assert self._cams is not None
        bgr = _decode_image_bytes(image_bytes)
        img_rgb = _circular_crop_and_pad(bgr, V8_INPUT_SIZE)
        rgb01 = img_rgb.astype(np.float32) / 255.0
        tensor = _make_tensor_v8(img_rgb, self.device)

        with self._inference_lock:
            with torch.inference_mode():
                probs = torch.softmax(self._model(tensor), dim=1)[0].cpu().float().numpy()
            if target_class is None:
                target_class = int(np.argmax(probs))
            targets = [ClassifierOutputTarget(target_class)]
            tta_fns = (
                (lambda x: x,                         lambda c: c),
                (lambda x: torch.flip(x, [3]),        lambda c: np.flip(c, axis=1).copy()),
                (lambda x: torch.flip(x, [2]),        lambda c: np.flip(c, axis=0).copy()),
                (lambda x: torch.rot90(x, 2, [2, 3]), lambda c: np.rot90(c, 2).copy()),
            )
            cams_tta: dict[str, list[np.ndarray]] = {n: [] for n in self._cams}
            for tfwd, tback in tta_fns:
                t_in = tfwd(tensor)
                for name, ext in self._cams.items():
                    c = ext(input_tensor=t_in, targets=targets)[0]
                    cams_tta[name].append(tback(c))

        cams = {n: np.mean(np.stack(cs, 0), 0) for n, cs in cams_tta.items()}
        # Lesion-focused fusion: shallow stage gets the heaviest weight.
        fused = 0.25 * cams["deep"] + 0.30 * cams["mid"] + 0.45 * cams["shallow"]
        fused = _percentile_norm(fused, 30.0, 99.5)
        fused = gaussian_filter(fused, sigma=2.0)
        retina = _retina_mask(img_rgb, kernel_size=11, blur_size=15)
        fused = fused * retina
        if fused.max() > 0:
            fused = fused / fused.max()
        fused = np.power(fused, 1.5)
        overlay = show_cam_on_image(rgb01, fused, use_rgb=True)
        attn_area = float((fused > 0.40).sum() / max((retina > 0.5).sum(), 1))
        pred = int(np.argmax(probs))
        return {
            "heatmap_base64": _to_base64_jpeg(overlay),
            "grade_idx": pred,
            "grade_label": V8_GRADE_NAMES[pred],
            "confidence": float(probs[pred]),
            "attention_area": attn_area,
            "target_class": int(target_class),
        }


# ═══════════════════════════════════════════════════════════════════
# Cascade orchestrator (V5.1 → V8, ICDR clinical grade 0..4)
# ═══════════════════════════════════════════════════════════════════

@dataclass
class RetinopathyCascadeResult:
    clinical_grade: int  # 0..4 ICDR
    clinical_grade_label: str
    binary: DRBinaryResult
    severity: DRSeverityResult | None  # None when V5.1 says No DR


class RetinopathyService:
    """V5.1 binary gate → V8 severity grader. Maps to ICDR clinical 0..4."""

    def __init__(self):
        self.binary = DRBinaryService()
        self.severity = DRSeverityService()

    @property
    def is_loaded(self) -> bool:
        return self.binary.is_loaded and self.severity.is_loaded

    def predict_cascade(self, image_bytes: bytes) -> RetinopathyCascadeResult:
        binary = self.binary.predict(image_bytes)
        if not binary.dr_detected:
            return RetinopathyCascadeResult(
                clinical_grade=0,
                clinical_grade_label=CLINICAL_GRADE_LABELS[0],
                binary=binary,
                severity=None,
            )
        severity = self.severity.predict(image_bytes)
        # V8 grade_idx 0..3 (Mild..Proliferative) → clinical 1..4 ICDR.
        clinical = severity.grade_idx + 1
        return RetinopathyCascadeResult(
            clinical_grade=clinical,
            clinical_grade_label=CLINICAL_GRADE_LABELS[clinical],
            binary=binary,
            severity=severity,
        )
