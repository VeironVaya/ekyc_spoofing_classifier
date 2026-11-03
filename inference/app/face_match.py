import cv2
import numpy as np
from deepface import DeepFace

MODEL_NAME = "ArcFace"


def verify_faces(id_card_bytes: bytes, selfie_bytes: bytes) -> dict:
    id_card_img = _decode_image(id_card_bytes)
    selfie_img = _decode_image(selfie_bytes)

    try:
        result = DeepFace.verify(
            img1_path=id_card_img,
            img2_path=selfie_img,
            model_name=MODEL_NAME,
        )
    except ValueError as exc:
        # DeepFace wraps the real reason (usually "face could not be detected
        # in img1/img2") in a generic "Exception while processing imgN_path"
        # and chains the original as __cause__ - unwrap it so the message is
        # actually actionable instead of just naming which image failed.
        reason = str(exc.__cause__) if exc.__cause__ is not None else str(exc)
        return {"verified": False, "distance": None, "threshold": None, "error": reason}

    return {
        "verified": bool(result["verified"]),
        "distance": float(result["distance"]),
        "threshold": float(result["threshold"]),
        "error": None,
    }


def _decode_image(image_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image")
    return img
