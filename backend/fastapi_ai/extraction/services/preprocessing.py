"""Image preprocessing service for OCR optimization."""

import cv2
import numpy as np
from PIL import Image, ImageOps, ImageFilter
import io
import logging

logger = logging.getLogger(__name__)

def optimize_image_for_ocr(file_bytes: bytes, mime_type: str) -> bytes:
    """
    Apply a series of image processing steps to improve OCR accuracy.
    Only processes image types. PDFs are returned as-is for Azure to handle.
    """
    if "pdf" in mime_type.lower():
        return file_bytes

    try:
        # Load image from bytes
        nparr = np.frombuffer(file_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            logger.warning("Failed to decode image for preprocessing")
            return file_bytes

        # 1. Convert to Grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 2. Rescaling (DPI check)
        # OCR works best at ~300 DPI. If the image is too small, we upscale.
        height, width = gray.shape[:2]
        if width < 1000 or height < 1000:
            interpolation = cv2.INTER_CUBIC
            gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=interpolation)

        # 3. Denoising
        # Non-local Means Denoising is effective but can be slow. 
        # Using a simpler Gaussian Blur or Median Blur for speed.
        denoised = cv2.medianBlur(gray, 3)

        # 4. Contrast Enhancement (CLAHE - Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(denoised)

        # 5. Adaptive Thresholding (Binarization)
        # Note: Sometimes Azure prefers the grayscale/enhanced image over pure black and white.
        # We will return the enhanced grayscale image as it's generally safer.
        # thresholded = cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        
        # 6. Deskewing
        deskewed = _deskew(enhanced)

        # Encode back to bytes
        _, buffer = cv2.imencode(".jpg", deskewed, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
        return buffer.tobytes()

    except Exception as exc:
        logger.error(f"Preprocessing failed: {exc}", exc_info=True)
        return file_bytes

def _deskew(image):
    """Detect and correct text skew."""
    try:
        # Invert the image (text becomes white, background black)
        thresh = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
        
        # Find coordinates of all non-zero pixels
        coords = np.column_stack(np.where(thresh > 0))
        
        # Find the minimum area rectangle that covers all pixels
        angle = cv2.minAreaRect(coords)[-1]
        
        # Adjust angle
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
            
        # If the angle is very small, don't bother rotating
        if abs(angle) < 0.5:
            return image

        # Rotate the image
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        
        return rotated
    except:
        return image
