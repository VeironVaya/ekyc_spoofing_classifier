import cv2
import numpy as np
import torch

# Must match training exactly (notebook: crop-center-aug-poluteprinted-tta-moire,
# transform_conv cell: A.Resize(256,256) + A.Normalize(imagenet mean/std)).
# Implemented directly with cv2/numpy instead of albumentations - resize and
# normalize are the only two ops used here, and this is mathematically
# identical to what those two albumentations transforms do.
IMG_SIZE = 256
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def decode_image(image_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image")
    return img


def resize_and_normalize(img: np.ndarray) -> torch.Tensor:
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = cv2.resize(img, (IMG_SIZE, IMG_SIZE), interpolation=cv2.INTER_LINEAR)

    img = img.astype(np.float32) / 255.0
    img = (img - IMAGENET_MEAN) / IMAGENET_STD
    img = np.transpose(img, (2, 0, 1))

    tensor = torch.from_numpy(img).float().unsqueeze(0)
    return tensor


def preprocess_image(image_bytes: bytes) -> torch.Tensor:
    return resize_and_normalize(decode_image(image_bytes))
