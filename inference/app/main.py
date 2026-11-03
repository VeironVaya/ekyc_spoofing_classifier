import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

import torch
from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from app.face_match import verify_faces
from app.ktp_forgery import init_ktp_forgery_model, predict_ktp_forgery, ktp_model
from app.model_loader import load_model
from app.ocr import extract_id_fields
from app.preprocess import decode_image, resize_and_normalize
from app.quality import score_quality
from app.schemas import (
    CompletePipelineResponse,
    EkycCheckResponse,
    FaceMatchResult,
    HealthResponse,
    ImageQuality,
    InferenceResponse,
    KtpForgeryResponse,
    OCRFields,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("inference")

MODEL_PATH = os.getenv("MODEL_PATH", "model/model_fold_0.pth")

# Fixed class order for Face Liveness PAD model
CLASSES = [
    "fake_mannequin",
    "fake_mask",
    "fake_printed",
    "fake_screen",
    "fake_unknown",
    "realperson",
]

model: torch.nn.Module | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model
    logger.info("Loading Face Liveness model from %s", MODEL_PATH)
    try:
        model = load_model(MODEL_PATH)
        logger.info("Face Liveness model loaded")
    except Exception as exc:
        logger.warning("Could not load Face Liveness model (%s): %s", MODEL_PATH, exc)

    # Initialize KTP Forgery model or heuristic engine
    init_ktp_forgery_model()
    yield


app = FastAPI(title="Liveness & e-KYC Inference Service", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    from app.ktp_forgery import ktp_model
    return HealthResponse(
        status="ok",
        model_loaded=model is not None,
        ktp_model_loaded=ktp_model is not None,
    )


@app.post("/infer", response_model=InferenceResponse)
async def infer(file: UploadFile = File(...)) -> InferenceResponse:
    if model is None:
        raise HTTPException(status_code=503, detail="Face Liveness model not loaded")

    image_bytes = await file.read()
    try:
        img = decode_image(image_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    quality = score_quality(img)
    if not quality["quality_passed"]:
        return InferenceResponse(
            predicted_class="",
            confidence=0.0,
            is_live=False,
            all_scores={},
            **quality,
        )

    tensor = resize_and_normalize(img)

    with torch.no_grad():
        logits = model(tensor)
        probs = torch.softmax(logits, dim=1).squeeze(0)

    all_scores = {cls: float(probs[i]) for i, cls in enumerate(CLASSES)}
    pred_idx = int(torch.argmax(probs).item())
    predicted_class = CLASSES[pred_idx]

    return InferenceResponse(
        predicted_class=predicted_class,
        confidence=all_scores[predicted_class],
        is_live=predicted_class == "realperson",
        all_scores=all_scores,
        **quality,
    )


@app.post("/ktp-forgery", response_model=KtpForgeryResponse)
async def ktp_forgery(
    file: UploadFile = File(...),
    mock_class: Optional[str] = Form(None),
) -> KtpForgeryResponse:
    """
    Mode 4: Standalone KTP Document Presentation Attack Detection (Doc-PAD).
    Evaluates blur/brightness and classifies card into:
    real_ktp, fake_screen, fake_print, fake_template, other.
    """
    image_bytes = await file.read()
    try:
        result = predict_ktp_forgery(image_bytes, mock_class=mock_class)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return KtpForgeryResponse(**result)


@app.post("/ekyc-check", response_model=EkycCheckResponse)
async def ekyc_check(
    id_card: UploadFile = File(...),
    selfie: UploadFile = File(...),
) -> EkycCheckResponse:
    """
    Mode 2: Legacy eKYC Check (OCR + Face Match).
    """
    id_card_bytes = await id_card.read()
    selfie_bytes = await selfie.read()

    try:
        id_card_quality = score_quality(decode_image(id_card_bytes), require_face=False)
        selfie_quality = score_quality(decode_image(selfie_bytes), require_face=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not id_card_quality["quality_passed"] or not selfie_quality["quality_passed"]:
        return EkycCheckResponse(
            id_card_quality=ImageQuality(**id_card_quality),
            selfie_quality=ImageQuality(**selfie_quality),
        )

    ocr_fields, match_result = await asyncio.gather(
        asyncio.to_thread(extract_id_fields, id_card_bytes),
        asyncio.to_thread(verify_faces, id_card_bytes, selfie_bytes),
    )

    return EkycCheckResponse(
        ocr=OCRFields(**ocr_fields),
        face_match=FaceMatchResult(**match_result),
        id_card_quality=ImageQuality(**id_card_quality),
        selfie_quality=ImageQuality(**selfie_quality),
    )


@app.post("/pipeline-check", response_model=CompletePipelineResponse)
async def pipeline_check(
    id_card: UploadFile = File(...),
    selfie: UploadFile = File(...),
    mock_ktp_class: Optional[str] = Form(None),
) -> CompletePipelineResponse:
    """
    Mode 3: Complete Onboarding Pipeline.
    Runs:
    1. KTP Image Quality Gate
    2. KTP Forgery Detection (Doc-PAD: real_ktp vs fake_screen/print/template/other)
    3. KTP OCR Field Extraction (NIK, Name, DOB)
    4. Selfie Image Quality Gate
    5. Selfie Face Liveness PAD (realperson vs spoof)
    6. 1:1 ArcFace Face Matching (KTP portrait vs Selfie)
    Concurrently executed for minimal latency.
    """
    id_card_bytes = await id_card.read()
    selfie_bytes = await selfie.read()

    try:
        id_card_quality = score_quality(decode_image(id_card_bytes), require_face=False)
        selfie_quality = score_quality(decode_image(selfie_bytes), require_face=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not id_card_quality["quality_passed"] or not selfie_quality["quality_passed"]:
        return CompletePipelineResponse(
            id_card_quality=ImageQuality(**id_card_quality),
            selfie_quality=ImageQuality(**selfie_quality),
        )

    # Concurrently execute KTP Doc-PAD, OCR, Face Match
    async def run_ktp_forgery():
        return predict_ktp_forgery(id_card_bytes, mock_class=mock_ktp_class)

    async def run_ocr():
        return extract_id_fields(id_card_bytes)

    async def run_face_match():
        return verify_faces(id_card_bytes, selfie_bytes)

    ktp_forg_res, ocr_fields, match_result = await asyncio.gather(
        asyncio.to_thread(predict_ktp_forgery, id_card_bytes, mock_ktp_class),
        asyncio.to_thread(extract_id_fields, id_card_bytes),
        asyncio.to_thread(verify_faces, id_card_bytes, selfie_bytes),
    )

    # Selfie liveness
    selfie_liveness = None
    if model is not None:
        selfie_tensor = resize_and_normalize(decode_image(selfie_bytes))
        with torch.no_grad():
            s_logits = model(selfie_tensor)
            s_probs = torch.softmax(s_logits, dim=1).squeeze(0)
        s_scores = {cls: float(s_probs[i]) for i, cls in enumerate(CLASSES)}
        s_idx = int(torch.argmax(s_probs).item())
        s_pred = CLASSES[s_idx]
        selfie_liveness = InferenceResponse(
            predicted_class=s_pred,
            confidence=s_scores[s_pred],
            is_live=s_pred == "realperson",
            all_scores=s_scores,
            **selfie_quality,
        )

    return CompletePipelineResponse(
        ktp_forgery=KtpForgeryResponse(**ktp_forg_res),
        ocr=OCRFields(**ocr_fields),
        face_match=FaceMatchResult(**match_result),
        selfie_liveness=selfie_liveness,
        id_card_quality=ImageQuality(**id_card_quality),
        selfie_quality=ImageQuality(**selfie_quality),
    )
