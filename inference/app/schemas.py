from typing import Dict, Optional

from pydantic import BaseModel


class InferenceResponse(BaseModel):
    predicted_class: str
    confidence: float
    is_live: bool
    all_scores: Dict[str, float]


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool


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


class EkycCheckResponse(BaseModel):
    ocr: OCRFields
    face_match: FaceMatchResult
