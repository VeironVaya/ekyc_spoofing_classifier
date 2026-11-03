from typing import Dict, Optional

from pydantic import BaseModel


class InferenceResponse(BaseModel):
    predicted_class: str
    confidence: float
    is_live: bool
    all_scores: Dict[str, float]
    blur_score: float
    brightness_score: float
    face_area_ratio: float
    quality_passed: bool
    quality_reject_reason: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    ktp_model_loaded: bool = False


class OCRFields(BaseModel):
    nik: Optional[str]
    name: Optional[str]
    date_of_birth: Optional[str]
    raw_text: str


class FaceMatchResult(BaseModel):
    verified: bool
    distance: Optional[float]
    threshold: Optional[float]
    error: Optional[str]


class ImageQuality(BaseModel):
    blur_score: float
    brightness_score: float
    face_area_ratio: float
    quality_passed: bool
    quality_reject_reason: Optional[str] = None


class EkycCheckResponse(BaseModel):
    ocr: Optional[OCRFields] = None
    face_match: Optional[FaceMatchResult] = None
    id_card_quality: ImageQuality
    selfie_quality: ImageQuality


class KtpForgeryResponse(BaseModel):
    predicted_class: str
    confidence: float
    is_authentic: bool
    all_scores: Dict[str, float]
    is_dummy: bool = False
    blur_score: float
    brightness_score: float
    face_area_ratio: float = 0.0
    quality_passed: bool
    quality_reject_reason: Optional[str] = None


class CompletePipelineResponse(BaseModel):
    ktp_forgery: Optional[KtpForgeryResponse] = None
    ocr: Optional[OCRFields] = None
    face_match: Optional[FaceMatchResult] = None
    selfie_liveness: Optional[InferenceResponse] = None
    id_card_quality: ImageQuality
    selfie_quality: ImageQuality
