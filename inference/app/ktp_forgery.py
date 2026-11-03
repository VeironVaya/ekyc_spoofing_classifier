import os
import logging
from typing import Dict, Optional, Tuple

import cv2
import numpy as np
import torch
import timm

from app.preprocess import decode_image, resize_and_normalize
from app.quality import score_quality

logger = logging.getLogger("inference.ktp_forgery")

KTP_CLASSES = [
    "real_ktp",
    "fake_screen",
    "fake_print",
    "fake_template",
    "other",
]

# Path to the fine-tuned ConvNeXt-Small Doc-PAD model
MODEL_PATHS = [
    os.getenv("KTP_FORGERY_MODEL_PATH", ""),
    "inference/model/best_convnext_small_ktp_pad.pth",
    "model/best_convnext_small_ktp_pad.pth",
    "inference/model/ktp_forgery_model.pth",
    "model/ktp_forgery_model.pth",
]

ktp_model: Optional[torch.nn.Module] = None
model_source_file: Optional[str] = None


def init_ktp_forgery_model(device: str = "cpu") -> bool:
    """
    Attempts to locate and load the fine-tuned ConvNeXt-Small 5-class model.
    If not found, initializes graceful heuristic/dummy engine.
    """
    global ktp_model, model_source_file

    for path in MODEL_PATHS:
        if path and os.path.exists(path):
            try:
                logger.info("Loading KTP Forgery model from %s", path)
                model = timm.create_model(
                    "convnext_small.fb_in22k_ft_in1k",
                    pretrained=False,
                    num_classes=len(KTP_CLASSES),
                )
                checkpoint = torch.load(path, map_location=device, weights_only=True)
                if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
                    checkpoint = checkpoint["state_dict"]
                elif isinstance(checkpoint, dict) and "model" in checkpoint:
                    checkpoint = checkpoint["model"]

                state_dict = {k.replace("module.", ""): v for k, v in checkpoint.items()}
                model.load_state_dict(state_dict)
                model.to(device)
                model.eval()

                ktp_model = model
                model_source_file = path
                logger.info("KTP Forgery ConvNeXt model successfully loaded from %s", path)
                return True
            except Exception as e:
                logger.warning("Failed loading KTP model from %s: %s", path, e)

    logger.info("KTP Forgery model weights not found. Operating in heuristic dummy mode.")
    ktp_model = None
    model_source_file = None
    return False


def _heuristic_doc_pad(img: np.ndarray, mock_class: Optional[str] = None) -> Tuple[str, float, Dict[str, float]]:
    """
    Intelligent heuristic fallback when PyTorch weights are not yet dropped into model/.
    Generates realistic probability distribution or honors mock_class for UI testing.
    """
    if mock_class and mock_class in KTP_CLASSES:
        chosen = mock_class
        conf = 0.942
        scores = {}
        rem = (1.0 - conf) / (len(KTP_CLASSES) - 1)
        for c in KTP_CLASSES:
            scores[c] = round(conf if c == chosen else rem + np.random.uniform(-0.01, 0.01), 4)
        # Normalize sum to 1.0
        total = sum(scores.values())
        scores = {k: round(v / total, 4) for k, v in scores.items()}
        return chosen, scores[chosen], scores

    # Inspect image geometry & color
    h, w = img.shape[:2]
    aspect_ratio = max(w, h) / max(min(w, h), 1)  # KTP standard ratio is ~1.58

    # Convert to HSV to check blue card header and background
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    blue_mask = cv2.inRange(hsv, np.array([90, 40, 40]), np.array([135, 255, 255]))
    blue_ratio = np.count_nonzero(blue_mask) / (h * w)

    # Laplacian variance for high-frequency sharpness
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()

    if blue_ratio < 0.05 and abs(aspect_ratio - 1.58) > 0.4:
        # Non-KTP card / document
        chosen = "other"
        conf = 0.912
    elif lap_var < 50.0:
        # Low frequency or screen glare
        chosen = "fake_screen"
        conf = 0.885
    else:
        # Authentic card
        chosen = "real_ktp"
        conf = 0.934

    scores = {}
    rem = (1.0 - conf) / (len(KTP_CLASSES) - 1)
    for c in KTP_CLASSES:
        scores[c] = round(conf if c == chosen else rem, 4)
    total = sum(scores.values())
    scores = {k: round(v / total, 4) for k, v in scores.items()}

    return chosen, scores[chosen], scores


def predict_ktp_forgery(image_bytes: bytes, mock_class: Optional[str] = None) -> Dict:
    """
    Main entry point for KTP Presentation Attack Detection (Doc-PAD).
    Evaluates blur/brightness quality, then executes model or heuristic.
    """
    img = decode_image(image_bytes)
    quality = score_quality(img, require_face=False)

    if not quality["quality_passed"]:
        return {
            "predicted_class": "",
            "confidence": 0.0,
            "is_authentic": False,
            "all_scores": {},
            "is_dummy": ktp_model is None,
            **quality,
        }

    # If real PyTorch model is loaded and no override requested
    if ktp_model is not None and not mock_class:
        tensor = resize_and_normalize(img)
        with torch.no_grad():
            logits = ktp_model(tensor)
            probs = torch.softmax(logits, dim=1).squeeze(0)

        all_scores = {cls: float(probs[i]) for i, cls in enumerate(KTP_CLASSES)}
        pred_idx = int(torch.argmax(probs).item())
        predicted_class = KTP_CLASSES[pred_idx]
        confidence = float(all_scores[predicted_class])
        is_dummy = False
    else:
        # Fallback to heuristic / mock simulation
        predicted_class, confidence, all_scores = _heuristic_doc_pad(img, mock_class=mock_class)
        is_dummy = True

    return {
        "predicted_class": predicted_class,
        "confidence": confidence,
        "is_authentic": predicted_class == "real_ktp",
        "all_scores": all_scores,
        "is_dummy": is_dummy,
        **quality,
    }

