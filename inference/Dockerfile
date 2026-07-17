FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgl1 \
    tesseract-ocr \
    tesseract-ocr-ind \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# CPU-only torch/torchvision build, pinned together from the CPU index - the
# target Azure VM has no GPU. Installed in one resolve so timm's unpinned
# torchvision dependency can't drag in a mismatched CUDA-enabled torch.
RUN pip install --no-cache-dir torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

# Bake the ArcFace weights into the image so containers never hit GitHub for
# them at request time - /root/.deepface isn't a persisted volume, so without
# this every container restart re-downloads ~130MB on the first /register call.
RUN python -c "from deepface import DeepFace; DeepFace.build_model('ArcFace')"

COPY app/ ./app/
COPY model/ ./model/

ENV MODEL_PATH=/app/model/model_fold_0.pth

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
