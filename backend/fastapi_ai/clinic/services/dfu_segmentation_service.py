from __future__ import annotations

import base64
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from threading import Lock

import cv2
import numpy as np
import segmentation_models_pytorch as smp
import torch
from PIL import Image
from torchvision import transforms

from clinic.config import resolve_pt_model_path


@dataclass
class DFUSegmentationPrediction:
    """Result of DFU segmentation inference."""
    ulcer_detected: bool
    threshold_used: float
    ulcer_area_ratio: float
    ulcer_area_px: float
    bbox_x: int
    bbox_y: int
    bbox_width_px: int
    bbox_height_px: int
    mask_base64: str
    overlay_base64: str


class DFUSegmenter:
    """DFU (Diabetic Foot Ulcer) segmentation service using ResNet34-UNet."""
    
    def __init__(self, model_path: Path | None = None, device: str = "cuda"):
        self.device = device
        self._model_path = model_path or self._resolve_model_path()
        self._model: smp.Unet | None = None
        self._lock = Lock()
        self._is_loaded = False
        
        self.transform = transforms.Compose([
            transforms.Resize((512, 512)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])

    @staticmethod
    def _resolve_model_path() -> Path:
        """Resolve DFU segmentation weights path."""
        # First try environment variable
        import os
        env_path = os.environ.get("DFU_SEGMENTATION_PATH")
        if env_path:
            return Path(env_path)
        
        # Default to clinic/models/DFUSegmentation
        clinic_dir = Path(__file__).resolve().parent.parent
        model_dir = clinic_dir / "models" / "DFUSegmentation"
        default_weights = model_dir / "resnet34_unet_weights.pth"
        
        if default_weights.exists():
            return default_weights
        
        raise FileNotFoundError(
            f"DFU segmentation model not found at {default_weights}. "
            f"Set DFU_SEGMENTATION_PATH environment variable or place weights at {default_weights}"
        )

    @property
    def checkpoint_path(self) -> Path:
        """Return the model checkpoint path."""
        return self._model_path

    @property
    def is_loaded(self) -> bool:
        """Check if model is currently loaded."""
        return self._is_loaded

    def ensure_loaded(self) -> None:
        """Load model if not already loaded."""
        if self._is_loaded:
            return
        
        with self._lock:
            if self._is_loaded:
                return
            
            if not self._model_path.exists():
                raise FileNotFoundError(f"Model checkpoint not found: {self._model_path}")
            
            try:
                # Initialize UNet model
                self._model = smp.Unet(
                    encoder_name="resnet34",
                    encoder_weights=None,
                    in_channels=3,
                    classes=1,
                    activation=None,
                )
                
                # Load checkpoint
                checkpoint = torch.load(self._model_path, map_location=self.device, weights_only=False)
                
                # Handle different checkpoint formats
                if isinstance(checkpoint, dict):
                    if "state_dict" in checkpoint:
                        state_dict = checkpoint["state_dict"]
                    elif "model_state_dict" in checkpoint:
                        state_dict = checkpoint["model_state_dict"]
                    else:
                        state_dict = checkpoint
                else:
                    state_dict = checkpoint
                
                self._model.load_state_dict(state_dict)
                self._model.to(self.device).eval()
                self._is_loaded = True
                
            except Exception as exc:
                self._model = None
                self._is_loaded = False
                raise RuntimeError(f"Failed to load DFU segmentation model: {exc}") from exc

    def predict(self, image_bytes: bytes, threshold: float = 0.5) -> DFUSegmentationPrediction:
        """
        Predict DFU segmentation from image bytes.
        
        Args:
            image_bytes: Raw image bytes (PNG, JPEG, etc.)
            threshold: Segmentation mask threshold in [0, 1]
        
        Returns:
            DFUSegmentationPrediction with detection results and visualizations
        
        Raises:
            FileNotFoundError: If model checkpoint not found
            RuntimeError: If model fails to load
            ValueError: If image cannot be decoded
        """
        self.ensure_loaded()
        
        if not (0.0 <= threshold <= 1.0):
            raise ValueError(f"Threshold must be in [0, 1], got {threshold}")
        
        # Decode image
        try:
            arr = np.frombuffer(image_bytes, np.uint8)
            img_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img_bgr is None:
                raise ValueError("Could not decode image from bytes")
        except Exception as exc:
            raise ValueError(f"Failed to decode image: {exc}") from exc
        
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        original_img = Image.fromarray(img_rgb)
        original_h, original_w = img_rgb.shape[:2]
        
        # Preprocess for model
        x = self.transform(original_img).unsqueeze(0).to(self.device)
        
        # Inference with TTA (Test-Time Augmentation)
        with torch.no_grad():
            # Original
            l1 = self._model(x)
            # Horizontal flip
            l2 = torch.flip(self._model(torch.flip(x, [3])), [3])
            # Vertical flip
            l3 = torch.flip(self._model(torch.flip(x, [2])), [2])
            # Average
            logits = (l1 + l2 + l3) / 3.0
            
            # Apply sigmoid and get probability map
            probs_map = torch.sigmoid(logits)[0, 0].cpu().numpy()
        
        # Generate binary mask
        mask = (probs_map >= threshold).astype(np.uint8)
        
        # Resize mask back to original dimensions
        mask_orig = cv2.resize(mask, (original_w, original_h), interpolation=cv2.INTER_NEAREST)
        
        # Calculate metrics
        ulcer_area_px = float(mask_orig.sum())
        ulcer_area_ratio = float(ulcer_area_px / (original_h * original_w))
        ulcer_detected = ulcer_area_ratio >= 0.001  # At least 0.1% area
        
        # Find bounding box
        coords = np.where(mask_orig > 0)
        if len(coords[0]) > 0:
            bbox_y1, bbox_y2 = coords[0].min(), coords[0].max()
            bbox_x1, bbox_x2 = coords[1].min(), coords[1].max()
            bbox_x = int(bbox_x1)
            bbox_y = int(bbox_y1)
            bbox_width_px = int(bbox_x2 - bbox_x1)
            bbox_height_px = int(bbox_y2 - bbox_y1)
        else:
            bbox_x = bbox_y = 0
            bbox_width_px = bbox_height_px = 0
        
        # Generate mask visualization (base64)
        mask_img = Image.fromarray((mask_orig * 255).astype(np.uint8))
        mask_buffer = BytesIO()
        mask_img.save(mask_buffer, format="PNG")
        mask_base64 = base64.b64encode(mask_buffer.getvalue()).decode("utf-8")
        
        # Generate overlay visualization (base64)
        overlay_rgb = img_rgb.copy()
        overlay_rgb[mask_orig > 0] = [
            int(0.3 * overlay_rgb[mask_orig > 0, 0] + 0.7 * 255),
            int(0.3 * overlay_rgb[mask_orig > 0, 1]),
            int(0.3 * overlay_rgb[mask_orig > 0, 2]),
        ]
        overlay_img = Image.fromarray(overlay_rgb.astype(np.uint8))
        overlay_buffer = BytesIO()
        overlay_img.save(overlay_buffer, format="PNG")
        overlay_base64 = base64.b64encode(overlay_buffer.getvalue()).decode("utf-8")
        
        return DFUSegmentationPrediction(
            ulcer_detected=ulcer_detected,
            threshold_used=threshold,
            ulcer_area_ratio=ulcer_area_ratio,
            ulcer_area_px=ulcer_area_px,
            bbox_x=bbox_x,
            bbox_y=bbox_y,
            bbox_width_px=bbox_width_px,
            bbox_height_px=bbox_height_px,
            mask_base64=mask_base64,
            overlay_base64=overlay_base64,
        )
