import asyncio
import logging
import os
from contextlib import asynccontextmanager

import torch
from fastapi import FastAPI, File, HTTPException, UploadFile

from app.face_match import verify_faces
from app.model_loader import load_model
from app.ocr import extract_id_fields
from app.preprocess import preprocess_image
from app.schemas import (
    EkycCheckResponse,
    FaceMatchResult,
    HealthResponse,
    InferenceResponse,
    OCRFields,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("inference")

MODEL_PATH = os.getenv("MODEL_PATH", "model/model_fold_0.pth")

# Fixed class order the model was trained on - do not reorder.
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
    logger.info("Loading model from %s", MODEL_PATH)
    model = load_model(MODEL_PATH)
    logger.info("Model loaded")
    yield


app = FastAPI(title="Liveness Inference Service", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", model_loaded=model is not None)


@app.post("/infer", response_model=InferenceResponse)
async def infer(file: UploadFile = File(...)) -> InferenceResponse:
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    image_bytes = await file.read()
    try:
        tensor = preprocess_image(image_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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
    )


@app.post("/ekyc-check", response_model=EkycCheckResponse)
async def ekyc_check(
    id_card: UploadFile = File(...),
    selfie: UploadFile = File(...),
) -> EkycCheckResponse:
    id_card_bytes = await id_card.read()
    selfie_bytes = await selfie.read()

    # OCR and face-match don't depend on each other - run them concurrently
    # instead of back-to-back to cut wall-clock latency.
    ocr_fields, match_result = await asyncio.gather(
        asyncio.to_thread(extract_id_fields, id_card_bytes),
        asyncio.to_thread(verify_faces, id_card_bytes, selfie_bytes),
    )

    return EkycCheckResponse(
        ocr=OCRFields(**ocr_fields),
        face_match=FaceMatchResult(**match_result),
    )
