import os

import cv2
import numpy as np

# Canonical size quality scores are computed at, independent of whatever size
# each caller happens to decode at - keeps BLUR_THRESHOLD comparable across a
# 4000x3000 phone photo and a 640x480 webcam frame.
QUALITY_SCORE_SIZE = 256

# Starting points only - not calibrated against real captures, expect a
# tuning pass once real webcam/phone traffic is available.
BLUR_THRESHOLD = float(os.getenv("BLUR_THRESHOLD", "100.0"))
BRIGHTNESS_MIN = float(os.getenv("BRIGHTNESS_MIN", "40.0"))
BRIGHTNESS_MAX = float(os.getenv("BRIGHTNESS_MAX", "215.0"))
MIN_IMAGE_WIDTH = float(os.getenv("MIN_IMAGE_WIDTH", "320.0"))
MIN_IMAGE_HEIGHT = float(os.getenv("MIN_IMAGE_HEIGHT", "240.0"))
# Deliberately low - this only needs to catch "no face" / "face is a
# speck in the corner", not enforce composition. An ID card photo has the
# face occupy a small fraction of the whole card scan, unlike a selfie.
MIN_FACE_AREA_RATIO = float(os.getenv("MIN_FACE_AREA_RATIO", "0.005"))

# Haar cascade, not a DNN detector - it ships inside opencv-python (no extra
# model file to fetch/manage) and is roughly what DeepFace's own default
# detector falls back to, so a reject here correlates with what would
# otherwise fail much later - and more confusingly - inside face-match.
_FACE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

# Cap the side length face detection runs at, for speed - full phone-camera
# resolution is unnecessary here. Detection still runs on an aspect-ratio-
# preserving resize (unlike the square QUALITY_SCORE_SIZE canonical resize
# used for blur/brightness), so a face isn't stretched out of shape.
FACE_DETECT_MAX_DIM = 800.0

# Master toggle for Quality Gating across all pipelines.
# Deactivated (False) by default per user request, so extreme/meme/blurry captures
# proceed directly to classifier models without getting blocked.
# Can be re-enabled anytime by setting ENABLE_QUALITY_GATING=true in environment.
ENABLE_QUALITY_GATING = os.getenv("ENABLE_QUALITY_GATING", "false").lower() in ("true", "1", "yes")


def score_quality(img_bgr: np.ndarray, require_face: bool = True) -> dict:
    height, width = img_bgr.shape[:2]

    resized = cv2.resize(img_bgr, (QUALITY_SCORE_SIZE, QUALITY_SCORE_SIZE), interpolation=cv2.INTER_LINEAR)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)

    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness_score = float(gray.mean())
    face_area_ratio = _largest_face_area_ratio(img_bgr) if require_face else 0.0

    reject_reason = None
    if ENABLE_QUALITY_GATING:
        if width < MIN_IMAGE_WIDTH or height < MIN_IMAGE_HEIGHT:
            reject_reason = "resolution_too_low"
        elif blur_score < BLUR_THRESHOLD:
            reject_reason = "too_blurry"
        elif brightness_score < BRIGHTNESS_MIN:
            reject_reason = "too_dark"
        elif brightness_score > BRIGHTNESS_MAX:
            reject_reason = "too_bright"
        elif require_face and face_area_ratio == 0.0:
            reject_reason = "no_face_detected"
        elif require_face and face_area_ratio < MIN_FACE_AREA_RATIO:
            reject_reason = "face_too_small"

    return {
        "blur_score": blur_score,
        "brightness_score": brightness_score,
        "face_area_ratio": face_area_ratio,
        "quality_passed": reject_reason is None,
        "quality_reject_reason": reject_reason,
    }


def _largest_face_area_ratio(img_bgr: np.ndarray) -> float:
    height, width = img_bgr.shape[:2]
    scale = min(1.0, FACE_DETECT_MAX_DIM / max(height, width))
    detect_img = (
        cv2.resize(img_bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1.0 else img_bgr
    )
    detect_gray = cv2.cvtColor(detect_img, cv2.COLOR_BGR2GRAY)

    faces = _FACE_CASCADE.detectMultiScale(detect_gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    if len(faces) == 0:
        return 0.0

    detect_area = detect_img.shape[0] * detect_img.shape[1]
    largest_face_area = max(w * h for (_, _, w, h) in faces)
    return largest_face_area / detect_area
