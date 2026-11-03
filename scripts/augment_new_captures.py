#!/usr/bin/env python3
"""
Targeted 6-Type Augmentation & Sequential ID Renaming Script

Processes newly captured KTP images in datasets/split/train/:
- real_ktp: 6 images (WIN_20261103_08_06_28_Pro.jpg -> WIN_20261103_08_08_42_Pro.jpg)
- fake_print: 8 images (WIN_20261103_08_07_04_Pro.jpg -> WIN_20261103_08_08_05_Pro.jpg)

Renames each original to the next available sequential ID:
- real_ktp: begins at 0505 (last existing: 0504) -> IDs 0505 to 0546 (42 files)
- fake_print: begins at 0577 (last existing: 0576) -> IDs 0577 to 0632 (56 files)

Generates 6 augmentations per original (1 each):
1. Brightness (factor = 1.25)
2. Gaussian Blur (ksize = (7, 7))
3. Rotation (angle = 5.0 deg, reflection border)
4. Center Crop (scale = 0.85, resized back to original shape)
5. Monochrome (3-channel grayscale)
6. Contrast (factor = 1.30, centered around 128)

Updates datasets/split/train/labels.csv and datasets/metadata/train_labels.csv (+98 rows).
Saves datasets/metadata/new_captures_augmentation_manifest.json for full traceability.
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

import cv2
import numpy as np
import pandas as pd


# --- Augmentation Functions ---

def augment_brightness(img_bgr: np.ndarray, factor: float = 1.25) -> np.ndarray:
    """Adjust brightness by scaling RGB values."""
    scaled = img_bgr.astype(np.float32) * factor
    return np.clip(scaled, 0, 255).astype(np.uint8)


def augment_blur(img_bgr: np.ndarray, ksize: Tuple[int, int] = (7, 7)) -> np.ndarray:
    """Apply Gaussian blur with given kernel size."""
    return cv2.GaussianBlur(img_bgr, ksize, 0)


def augment_rotation(img_bgr: np.ndarray, angle: float = 5.0) -> np.ndarray:
    """Rotate image around center using border reflection to avoid black corners."""
    h, w = img_bgr.shape[:2]
    center = (w / 2.0, h / 2.0)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(img_bgr, matrix, (w, h), borderMode=cv2.BORDER_REFLECT_101)


def augment_center_crop(img_bgr: np.ndarray, scale: float = 0.85) -> np.ndarray:
    """Center crop by scale factor and resize back to original dimensions."""
    h, w = img_bgr.shape[:2]
    crop_w, crop_h = int(w * scale), int(h * scale)
    x1 = (w - crop_w) // 2
    y1 = (h - crop_h) // 2
    cropped = img_bgr[y1 : y1 + crop_h, x1 : x1 + crop_w]
    return cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)


def augment_monochrome(img_bgr: np.ndarray) -> np.ndarray:
    """Convert image to 3-channel grayscale / monochrome photocopy simulation."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def augment_contrast(img_bgr: np.ndarray, factor: float = 1.30) -> np.ndarray:
    """Adjust contrast centered around midpoint luminance (128)."""
    adjusted = 128.0 + factor * (img_bgr.astype(np.float32) - 128.0)
    return np.clip(adjusted, 0, 255).astype(np.uint8)


AUGMENTATION_TYPES = [
    ("bright", "Brightness (factor=1.25)", lambda img: augment_brightness(img, 1.25)),
    ("blur", "Gaussian Blur (k=7x7)", lambda img: augment_blur(img, (7, 7))),
    ("rot", "Rotation (angle=+5deg)", lambda img: augment_rotation(img, 5.0)),
    ("crop", "Center Crop (scale=0.85)", lambda img: augment_center_crop(img, 0.85)),
    ("mono", "Monochrome Grayscale", lambda img: augment_monochrome(img)),
    ("contrast", "Contrast (factor=1.30)", lambda img: augment_contrast(img, 1.30)),
]


def get_highest_id(folder: Path) -> int:
    """Finds the highest numeric prefix among files like 0504_real_ktp.png."""
    ids = []
    if folder.exists():
        for f in folder.iterdir():
            if f.is_file():
                match = re.match(r"^(\d{4})_", f.name)
                if match:
                    ids.append(int(match.group(1)))
    return max(ids) if ids else 0


def run_pipeline():
    repo_root = Path(__file__).resolve().parent.parent
    train_dir = repo_root / "datasets" / "split" / "train"
    metadata_dir = repo_root / "datasets" / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)

    targets = {
        "real_ktp": {
            "dir": train_dir / "real_ktp",
            "label_id": 0,
            "pattern": "WIN_20261103_08*.jpg",
        },
        "fake_print": {
            "dir": train_dir / "fake_print",
            "label_id": 2,
            "pattern": "WIN_20261103_08*.jpg",
        },
    }

    manifest = {}
    new_csv_records = []

    print("=" * 75)
    print("🚀 TARGETED 6-TYPE AUGMENTATION & SEQUENTIAL ID RENAMING")
    print("=" * 75)

    for class_name, cfg in targets.items():
        folder = cfg["dir"]
        label_id = cfg["label_id"]

        if not folder.exists():
            print(f"❌ Directory not found: {folder}")
            continue

        highest_id = get_highest_id(folder)
        start_id = highest_id + 1
        current_id = start_id

        win_files = sorted(list(folder.glob(cfg["pattern"])))
        print(f"\n📂 Processing class: {class_name}")
        print(f"   Folder: {folder}")
        print(f"   Highest existing ID: {highest_id:04d}")
        print(f"   Next ID starting at: {start_id:04d}")
        print(f"   New captures found : {len(win_files)} images")

        if not win_files:
            print(f"   ⚠️ No files matching '{cfg['pattern']}' found. Skipping.")
            continue

        for src_file in win_files:
            orig_filename = src_file.name
            img_bgr = cv2.imread(str(src_file))
            if img_bgr is None:
                print(f"   ⚠️ Could not read {orig_filename}. Skipping.")
                continue

            # 1. Rename Original Image to Sequential ID
            orig_id = current_id
            renamed_name = f"{orig_id:04d}_{class_name}.jpg"
            renamed_path = folder / renamed_name

            # Remove the source WIN file and write as renamed file
            src_file.unlink()
            cv2.imwrite(str(renamed_path), img_bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])

            manifest[renamed_name] = {
                "source_win_filename": orig_filename,
                "role": "original",
                "augmentation_type": "none",
                "class_name": class_name,
                "label_id": label_id,
                "shape": list(img_bgr.shape),
            }

            new_csv_records.append({
                "filename": renamed_name,
                "relative_path": f"train/{class_name}/{renamed_name}",
                "class_name": class_name,
                "label_id": label_id,
            })

            print(f"   📄 [{orig_id:04d}] Original: {orig_filename} -> {renamed_name}")
            current_id += 1

            # 2. Generate 6 Augmentations Consecutively
            for aug_key, aug_desc, aug_func in AUGMENTATION_TYPES:
                aug_id = current_id
                aug_name = f"{aug_id:04d}_{class_name}.jpg"
                aug_path = folder / aug_name

                transformed = aug_func(img_bgr)
                cv2.imwrite(str(aug_path), transformed, [cv2.IMWRITE_JPEG_QUALITY, 95])

                manifest[aug_name] = {
                    "source_win_filename": orig_filename,
                    "parent_renamed_id": renamed_name,
                    "role": "augmentation",
                    "augmentation_type": aug_key,
                    "description": aug_desc,
                    "class_name": class_name,
                    "label_id": label_id,
                    "shape": list(transformed.shape),
                }

                new_csv_records.append({
                    "filename": aug_name,
                    "relative_path": f"train/{class_name}/{aug_name}",
                    "class_name": class_name,
                    "label_id": label_id,
                })

                current_id += 1

        end_id = current_id - 1
        total_class_created = end_id - start_id + 1
        print(f"   ✅ Finished '{class_name}': generated {total_class_created} files ({start_id:04d} -> {end_id:04d})")

    # 3. Save Traceability Manifest
    manifest_path = metadata_dir / "new_captures_augmentation_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"\n📋 Augmentation manifest written to: {manifest_path}")

    # 4. Update labels.csv files
    labels_csv_paths = [
        train_dir / "labels.csv",
        metadata_dir / "train_labels.csv",
    ]

    new_df = pd.DataFrame(new_csv_records)
    print(f"📊 New records to append: {len(new_df)} rows")

    for p in labels_csv_paths:
        if p.exists():
            existing_df = pd.read_csv(p)
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
            # Remove any potential duplicate filenames
            combined_df = combined_df.drop_duplicates(subset=["filename"])
            combined_df.to_csv(p, index=False)
            print(f"   Updated {p.name}: {len(existing_df)} -> {len(combined_df)} rows")
        else:
            new_df.to_csv(p, index=False)
            print(f"   Created {p.name} with {len(new_df)} rows")

    print("\n" + "=" * 75)
    print("🎉 ALL AUGMENTATIONS & RENAMING COMPLETED SUCCESSFULLY!")
    print("=" * 75)


if __name__ == "__main__":
    run_pipeline()
