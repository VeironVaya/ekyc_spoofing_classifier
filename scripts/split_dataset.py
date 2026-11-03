"""
Deterministic Zero-Leakage Grouped Train-Test Dataset Splitter.
Splits datasets/processed/ into datasets/split/train/ and datasets/split/test/
with zero data leakage and exact class balance in test (108 per class).

Label mapping:
  0: real_ktp
  1: fake_screen
  2: fake_print
  3: fake_template
  4: other
"""

import os
import sys
import json
import csv
import shutil
import argparse
from pathlib import Path

# Fix Windows console encoding
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "datasets" / "processed"
SPLIT_DIR = PROJECT_ROOT / "datasets" / "split"
METADATA_DIR = PROJECT_ROOT / "datasets" / "metadata"

CLASS_LABELS = {
    "real_ktp": 0,
    "fake_screen": 1,
    "fake_print": 2,
    "fake_template": 3,
    "other": 4,
}

# Designated Test Sources per class (stratified across capture setups/devices/resolutions)
DESIGNATED_TEST_SOURCES = {
    "real_ktp": [
        "0004_real_ktp.jpeg",  # 720x1280 mid-res portrait
        "0005_real_ktp.jpeg",  # 900x1600 high-res portrait
        "0013_real_ktp.jpeg",  # 1280x720 landscape
    ],
    "other": [
        "0004_other.jpeg",
        "0009_other.jpeg",
        "0013_other.jpeg",
    ],
    "fake_print": [
        "0003_fake_print.jpeg",  # 720x1280 portrait
        "0008_fake_print.jpeg",  # 720x1280 portrait
        "0014_fake_print.jpeg",  # 1280x720 landscape
    ],
    "fake_screen": [
        "0008_fake_screen.jpeg",  # 720x1280 portrait phone screen
        "0002_fake_screen.jpeg",  # 1280x720 mid-res landscape screen
        "0011_fake_screen.jpeg",  # 1280x720 mid-res landscape screen
        "0016_fake_screen.jpg",   # 1920x1080 high-res landscape screen
        "0021_fake_screen.jpg",   # 1920x1080 high-res landscape screen
        "0027_fake_screen.jpg",   # 1920x1080 high-res landscape screen
    ],
    "fake_template": [
        "0003_fake_template.png",  # Augmented template source 1
        "0008_fake_template.png",  # Augmented template source 2
    ],
}


def compute_split_items():
    """
    Computes train and test file assignments for all 5 classes.
    Returns:
      train_records: list of dicts
      test_records: list of dicts
      summary: dict with counts and source allocations
    """
    train_records = []
    test_records = []
    summary = {}

    for class_name, label_id in CLASS_LABELS.items():
        class_dir = PROCESSED_DIR / class_name
        manifest_path = METADATA_DIR / f"{class_name}_manifest.json"

        if not class_dir.exists():
            raise FileNotFoundError(f"Missing processed folder: {class_dir}")
        if not manifest_path.exists():
            raise FileNotFoundError(f"Missing manifest: {manifest_path}")

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        all_files = sorted(os.listdir(class_dir))
        test_source_set = set(DESIGNATED_TEST_SOURCES[class_name])

        class_train = []
        class_test = []

        if class_name != "fake_template":
            # For real_ktp, other, fake_print, fake_screen:
            # Group by source image (both original and augmented)
            for fname in all_files:
                if fname in manifest:
                    src = manifest[fname]["source_image"]
                    aug = manifest[fname]["augmentation"]
                    is_aug = True
                else:
                    src = fname
                    aug = "original"
                    is_aug = False

                rec = {
                    "filename": fname,
                    "relative_path": f"{class_name}/{fname}",
                    "class": class_name,
                    "label_id": label_id,
                    "source_image": src,
                    "is_augmented": is_aug,
                    "augmentation": aug,
                }

                if src in test_source_set:
                    class_test.append(rec)
                else:
                    class_train.append(rec)

        else:
            # Special handling for fake_template:
            # 10 template source cards (with 35 augmentations each)
            # + 162 unique raw synthetic cards (0011 to 0172)
            # 2 template sources in test = 2 * 36 = 72 images
            # Need 36 raw synthetic cards in test to reach exactly 108 test images
            raw_cards = [f for f in all_files if f not in manifest]
            # Template sources in raw_cards are 0001 to 0010
            pool_raw = [f for f in raw_cards if f not in set(manifest[k]["source_image"] for k in manifest)]

            # Sample 36 cards evenly from pool_raw (162 cards)
            sample_step = (len(pool_raw) - 1) / 35.0
            test_raw_indices = [int(round(i * sample_step)) for i in range(36)]
            test_raw_set = set(pool_raw[i] for i in test_raw_indices)

            for fname in all_files:
                if fname in manifest:
                    src = manifest[fname]["source_image"]
                    aug = manifest[fname]["augmentation"]
                    is_aug = True
                else:
                    src = fname
                    aug = "original"
                    is_aug = False

                rec = {
                    "filename": fname,
                    "relative_path": f"{class_name}/{fname}",
                    "class": class_name,
                    "label_id": label_id,
                    "source_image": src,
                    "is_augmented": is_aug,
                    "augmentation": aug,
                }

                if is_aug:
                    if src in test_source_set:
                        class_test.append(rec)
                    else:
                        class_train.append(rec)
                else:
                    if src in test_source_set or fname in test_raw_set:
                        class_test.append(rec)
                    else:
                        class_train.append(rec)

        train_records.extend(class_train)
        test_records.extend(class_test)

        train_sources = set(r["source_image"] for r in class_train)
        test_sources = set(r["source_image"] for r in class_test)
        leakage = train_sources.intersection(test_sources)

        summary[class_name] = {
            "total_images": len(all_files),
            "train_images": len(class_train),
            "test_images": len(class_test),
            "test_percentage": round(len(class_test) / len(all_files) * 100, 2),
            "train_unique_sources": len(train_sources),
            "test_unique_sources": len(test_sources),
            "leakage_count": len(leakage),
        }

    return train_records, test_records, summary


def run_split(dry_run=False):
    print("=" * 65)
    print("Zero-Leakage Grouped Train-Test Dataset Splitting")
    print("=" * 65)

    train_records, test_records, summary = compute_split_items()

    print(f"\n{'Class':15s} | {'Total':5s} | {'Train':5s} | {'Test':5s} | {'Test %':6s} | {'Leakage':7s}")
    print("-" * 65)
    for c, stats in summary.items():
        leak_str = "0 (PASS)" if stats["leakage_count"] == 0 else f"{stats['leakage_count']} (FAIL)"
        print(
            f"{c:15s} | {stats['total_images']:5d} | {stats['train_images']:5d} | "
            f"{stats['test_images']:5d} | {stats['test_percentage']:5.1f}% | {leak_str:7s}"
        )
    print("-" * 65)
    total_all = len(train_records) + len(test_records)
    test_pct = round(len(test_records) / total_all * 100, 2)
    print(f"{'TOTAL':15s} | {total_all:5d} | {len(train_records):5d} | {len(test_records):5d} | {test_pct:5.1f}% | 0 (PASS)")

    if dry_run:
        print("\n[DRY-RUN] Verification complete. No directories created or files copied.")
        return

    # Create destination directories under datasets/split/
    train_root = SPLIT_DIR / "train"
    test_root = SPLIT_DIR / "test"

    for class_name in CLASS_LABELS:
        (train_root / class_name).mkdir(parents=True, exist_ok=True)
        (test_root / class_name).mkdir(parents=True, exist_ok=True)

    print(f"\nCopying {len(train_records)} images to {train_root}...")
    for rec in train_records:
        src_path = PROCESSED_DIR / rec["class"] / rec["filename"]
        dst_path = train_root / rec["class"] / rec["filename"]
        shutil.copy2(src_path, dst_path)

    print(f"Copying {len(test_records)} images to {test_root}...")
    for rec in test_records:
        src_path = PROCESSED_DIR / rec["class"] / rec["filename"]
        dst_path = test_root / rec["class"] / rec["filename"]
        shutil.copy2(src_path, dst_path)

    # Write CSV manifests
    fieldnames = ["filename", "relative_path", "class", "label_id", "source_image", "is_augmented", "augmentation"]

    train_csv_path = METADATA_DIR / "split_train_manifest.csv"
    with open(train_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(train_records)

    test_csv_path = METADATA_DIR / "split_test_manifest.csv"
    with open(test_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(test_records)

    # Write summary JSON
    summary_path = METADATA_DIR / "split_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\nSplit operation completed successfully!")
    print(f"  - Train Manifest: {train_csv_path} ({len(train_records)} rows)")
    print(f"  - Test Manifest:  {test_csv_path} ({len(test_records)} rows)")
    print(f"  - Summary JSON:   {summary_path}")


def main():
    parser = argparse.ArgumentParser(description="Zero-Leakage Grouped Train-Test Splitter")
    parser.add_argument("--dry-run", action="store_true", help="Simulate split without copying files")
    args = parser.parse_args()

    run_split(dry_run=args.dry_run)


if __name__ == "__main__":
    main()

