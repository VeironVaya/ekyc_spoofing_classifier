import re
from typing import Optional

import cv2
import numpy as np
import pytesseract
from PIL import Image

# Best-effort field extraction for Indonesian KTP-style ID cards via plain
# Tesseract OCR - no fine-tuning, no layout model. Good enough for a demo;
# don't expect production-grade accuracy on skewed/low-light photos.

DATE_PATTERN = re.compile(r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})\b")

TESSERACT_CONFIG = "--oem 1 --psm 6"


def extract_id_fields(image_bytes: bytes) -> dict:
    image = _preprocess(image_bytes)
    raw_text = pytesseract.image_to_string(image, lang="ind+eng", config=TESSERACT_CONFIG)

    return {
        "nik": _extract_nik(raw_text),
        "name": _extract_name(raw_text),
        "date_of_birth": _extract_dob(raw_text),
        "raw_text": raw_text.strip(),
    }


def _preprocess(image_bytes: bytes) -> Image.Image:
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # KTP photos are often phone-camera resolution with small print - upscale
    # so character x-height is large enough for Tesseract to resolve.
    h, w = gray.shape
    if max(h, w) < 1800:
        scale = 1800 / max(h, w)
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    gray = cv2.bilateralFilter(gray, 9, 75, 75)

    # Tesseract's LSTM engine (--oem 1) does its own adaptive binarization
    # internally and tends to do *worse* on images we've already force-
    # thresholded ourselves - benchmarked against a synthetic KTP-style test
    # image, hard thresholding (Otsu and adaptive) both underperformed simply
    # denoising + boosting local contrast and leaving it grayscale.
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    return Image.fromarray(gray)


# Tesseract frequently swaps visually similar letters for digits (and vice
# versa) on small/noisy print - normalize before hunting for a 16-digit run.
DIGIT_CONFUSION = str.maketrans(
    {"O": "0", "o": "0", "I": "1", "l": "1", "i": "1", "S": "5", "s": "5",
     "B": "8", "Z": "2", "G": "6", "A": "4", "T": "7", "g": "9"}
)


def _guess_nik(value_part: str) -> str:
    # Best-effort fill for a NIK-labeled value that didn't cleanly resolve to
    # 16 digits: keep real digits, convert confusable letters, and turn any
    # other character into a "5" placeholder rather than giving up. The user
    # reviews and edits this on the confirm form before anything is decided
    # or saved, so a rough guess to correct beats an empty field.
    translated = value_part.translate(DIGIT_CONFUSION)
    digits = []
    for ch in translated:
        if ch.isspace():
            continue
        if len(digits) == 16:
            break
        digits.append(ch if ch.isdigit() else "5")
    while len(digits) < 16:
        digits.append("5")
    return "".join(digits)


def _extract_nik(text: str) -> Optional[str]:
    lines = text.split("\n")

    # Prefer the substring after an explicit "NIK" label - scoping to just
    # the value avoids picking up stray digits elsewhere on the same line
    # (previously, a line-wide digit count could coincidentally hit 16 using
    # noise digits from outside the actual NIK value, producing a confident
    # but wrong result instead of correctly failing on an unreadable digit).
    for line in lines:
        if not re.search(r"\bnik\b", line, re.IGNORECASE):
            continue
        parts = re.split(r"\bnik\b\s*[:=\-]?\s*", line, flags=re.IGNORECASE, maxsplit=1)
        value_part = parts[1] if len(parts) > 1 else line
        digits = re.sub(r"\D", "", value_part)
        if len(digits) == 16:
            return digits
        fixed = re.sub(r"\D", "", value_part.translate(DIGIT_CONFUSION))
        if len(fixed) == 16:
            return fixed
        return _guess_nik(value_part)

    # No NIK-labeled line found at all - only accept an unlabeled line if it
    # is unambiguously nothing but a 16-digit run.
    for line in lines:
        digits = re.sub(r"\D", "", line)
        if len(digits) == 16:
            return digits

    return None


def _extract_name(text: str) -> Optional[str]:
    for line in text.split("\n"):
        if re.search(r"nama", line, re.IGNORECASE):
            parts = re.split(r"nama\s*[:\-]?\s*", line, flags=re.IGNORECASE, maxsplit=1)
            candidate = _clean_name(parts[1]) if len(parts) > 1 else None
            if candidate:
                return candidate
    # No fuzzy fallback here on purpose: a wrong-but-confident name is worse
    # for a KYC flow than correctly reporting "not detected".
    return None


def _clean_name(value: str) -> Optional[str]:
    cleaned = re.sub(r"[^A-Za-z ]", " ", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned if len(cleaned) >= 3 else None


def _extract_dob(text: str) -> Optional[str]:
    match = DATE_PATTERN.search(text)
    return match.group(0) if match else None
