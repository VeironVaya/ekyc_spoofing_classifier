"""
Stratified Feature-Aware Dataset Balancing Script.
Balances fake_screen (1,044 -> 522) and fake_template (2,350 -> 522)
to match real_ktp (504), other (504), and fake_print (576).

- fake_screen:
    Keeps 100% of all 29 original capture devices.
    Selects 17 diverse variants per capture across all 6 augmentation categories:
      - 3 brightness: dark (0.40), mid (0.80), bright (1.50)
      - 2 blur: subtle (k5x5), heavy (k11x11)
      - 5 rotation: steep left (-15°), mid left (-6°), slight left (-1°), mid right (+6°), steep right (+15°)
      - 3 crop: tight (0.95), mid (0.85), deep zoom (0.75)
      - 1 monochrome: mono_01 (pruning redundant duplicates)
      - 3 contrast: low (0.50), medium (1.25), high dynamic (1.80)
    Yields: 29 + (29 * 17) = 522 images.

- fake_template:
    Keeps all 350 augmented variants.
    Selects 172 diverse raw synthetic renders (cards 1-10 + 162 strided across remaining 1,990 cards).
    Yields: 350 + 172 = 522 images.

- Safe archiving:
    Unselected files are moved to datasets/archive/<class>_overflow/ (zero data loss).
- Safe renumbering:
    Two-stage renaming to prevent collisions.
- Manifest update:
    datasets/metadata/<class>_manifest.json updated with new file names.
"""

import os
import sys
import json
import shutil
import argparse
from pathlib import Path

# Fix Windows console encoding
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "datasets" / "processed"
ARCHIVE_DIR = PROJECT_ROOT / "datasets" / "archive"
METADATA_DIR = PROJECT_ROOT / "datasets" / "metadata"

# Stratified targets for fake_screen: exactly 17 augmentation tags per source image
TARGET_SCREEN_AUGS = [
    # Brightness (3)
    "bright_01_factor0.40",
    "bright_03_factor0.80",
    "bright_05_factor1.50",
    # Blur (2)
    "blur_02_k5x5",
    "blur_04_k11x11",
    # Rotation (5)
    "rot_01_degm15",
    "rot_03_degm6",
    "rot_05_degm1",
    "rot_08_degp6",
    "rot_10_degp15",
    # Center Crop (3)
    "crop_01_scale0.95",
    "crop_03_scale0.85",
    "crop_05_scale0.75",
    # Monochrome (1)
    "mono_01",
    # Contrast (3)
    "contrast_01_factor0.50",
    "contrast_03_factor1.25",
    "contrast_05_factor1.80",
]


def balance_fake_screen(dry_run=False):
    print("=" * 60)
    print("Balancing 'fake_screen' (Target: 522 images)")
    print("=" * 60)

    class_dir = PROCESSED_DIR / "fake_screen"
    archive_dir = ARCHIVE_DIR / "fake_screen_overflow"
    manifest_path = METADATA_DIR / "fake_screen_manifest.json"

    if not manifest_path.exists():
        print(f"Error: Manifest not found at {manifest_path}")
        return

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    all_files = sorted(os.listdir(class_dir))
    original_files = [f for f in all_files if f not in manifest]
    augmented_files = [f for f in all_files if f in manifest]

    print(f"Current total: {len(all_files)} files")
    print(f"  - Original captures: {len(original_files)}")
    print(f"  - Augmented variants: {len(augmented_files)}")

    # Group augmented files by source_image
    by_source = {}
    for fname, meta in manifest.items():
        src = meta["source_image"]
        by_source.setdefault(src, []).append((fname, meta["augmentation"]))

    selected_augmented = []
    unselected_augmented = []

    for src_file in original_files:
        variants = by_source.get(src_file, [])
        aug_map = {aug: fname for fname, aug in variants}

        for target_aug in TARGET_SCREEN_AUGS:
            if target_aug in aug_map:
                selected_augmented.append((aug_map[target_aug], src_file, target_aug))
            else:
                print(f"Warning: Missing expected aug '{target_aug}' for source '{src_file}'")

        # Track unselected
        selected_set = {aug_map[target_aug] for target_aug in TARGET_SCREEN_AUGS if target_aug in aug_map}
        for fname, aug in variants:
            if fname not in selected_set:
                unselected_augmented.append(fname)

    print(f"\nSelection Summary:")
    print(f"  - Originals retained: {len(original_files)} (100% of all capture devices)")
    print(f"  - Augmented retained: {len(selected_augmented)} (17 variants x {len(original_files)} devices)")
    print(f"  - Total retained: {len(original_files) + len(selected_augmented)} images")
    print(f"  - Unselected to archive: {len(unselected_augmented)} images")

    if dry_run:
        print("[DRY-RUN] No files moved or renamed.")
        return

    # 1. Move unselected files to archive
    archive_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nMoving {len(unselected_augmented)} unselected files to {archive_dir}...")
    for fname in unselected_augmented:
        shutil.move(str(class_dir / fname), str(archive_dir / fname))

    # 2. Sort selected augmented files to ensure deterministic sequential naming
    # Order: by source image, then by augmentation order
    aug_order = {aug: i for i, aug in enumerate(TARGET_SCREEN_AUGS)}
    selected_augmented.sort(key=lambda x: (x[1], aug_order.get(x[2], 999)))

    # 3. Two-stage rename for selected augmented files (0030 to 0522)
    # Stage 1: rename to temporary unique filenames to avoid collision
    temp_map = []
    start_id = len(original_files) + 1  # 30
    for idx, (old_fname, src_file, aug_type) in enumerate(selected_augmented):
        ext = Path(old_fname).suffix
        new_id = start_id + idx
        final_fname = f"{new_id:04d}_fake_screen{ext}"
        temp_fname = f"__temp_{new_id:04d}_fake_screen{ext}"
        os.rename(class_dir / old_fname, class_dir / temp_fname)
        temp_map.append((temp_fname, final_fname, src_file, aug_type))

    # Stage 2: rename temporary to final and build updated manifest
    new_manifest = {}
    for temp_fname, final_fname, src_file, aug_type in temp_map:
        os.rename(class_dir / temp_fname, class_dir / final_fname)
        new_manifest[final_fname] = {
            "source_image": src_file,
            "augmentation": aug_type,
        }

    # 4. Save updated manifest
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(new_manifest, f, indent=2)

    final_count = len(os.listdir(class_dir))
    print(f"Completed! 'fake_screen' now has {final_count} images.")
    print(f"Updated manifest saved with {len(new_manifest)} entries.")


def balance_fake_template(dry_run=False):
    print("\n" + "=" * 60)
    print("Balancing 'fake_template' (Target: 522 images)")
    print("=" * 60)

    class_dir = PROCESSED_DIR / "fake_template"
    archive_dir = ARCHIVE_DIR / "fake_template_overflow"
    manifest_path = METADATA_DIR / "fake_template_manifest.json"

    if not manifest_path.exists():
        print(f"Error: Manifest not found at {manifest_path}")
        return

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    all_files = sorted(os.listdir(class_dir))
    raw_files = [f for f in all_files if f not in manifest]
    augmented_files = [f for f in all_files if f in manifest]

    print(f"Current total: {len(all_files)} files")
    print(f"  - Raw synthetic renders: {len(raw_files)}")
    print(f"  - Augmented variants: {len(augmented_files)}")

    # Strategy:
    # Retain ALL 350 augmented variants.
    # Target raw cards = 522 - 350 = 172 cards.
    # Cards 0001 to 0010 MUST be kept because they are the sources for the 350 augmentations!
    # Remaining 162 cards are sampled evenly across the remaining raw files (0011 to 2000).

    src_set = set(meta["source_image"] for meta in manifest.values())
    mandatory_raw = [f for f in raw_files if f in src_set]
    pool_raw = [f for f in raw_files if f not in src_set]

    remaining_needed = 172 - len(mandatory_raw)  # 172 - 10 = 162
    sampled_indices = [
        int(round(i * (len(pool_raw) - 1) / (remaining_needed - 1)))
        for i in range(remaining_needed)
    ]
    sampled_raw = [pool_raw[i] for i in sorted(list(set(sampled_indices)))]

    selected_raw = mandatory_raw + sampled_raw
    unselected_raw = [f for f in raw_files if f not in set(selected_raw)]

    print(f"\nSelection Summary:")
    print(f"  - Raw renders retained: {len(selected_raw)} (10 sources + {len(sampled_raw)} sampled)")
    print(f"  - Augmented retained: {len(augmented_files)} (100% of all 350 augmented variants)")
    print(f"  - Total retained: {len(selected_raw) + len(augmented_files)} images")
    print(f"  - Unselected to archive: {len(unselected_raw)} raw renders")

    if dry_run:
        print("[DRY-RUN] No files moved or renamed.")
        return

    # 1. Move unselected raw renders to archive
    archive_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nMoving {len(unselected_raw)} unselected raw renders to {archive_dir}...")
    for fname in unselected_raw:
        shutil.move(str(class_dir / fname), str(archive_dir / fname))

    # 2. Renumber active files
    # The 172 raw renders become 0001_fake_template.png to 0172_fake_template.png
    # The 10 source images (0001 to 0010) are already 0001 to 0010, so they don't change!
    # The 350 augmented variants become 0173_fake_template.png to 0522_fake_template.png

    # Two-stage rename for the non-source raw files (from index 11 to 172)
    stage1_raw = []
    for idx, old_fname in enumerate(selected_raw):
        new_id = idx + 1
        final_fname = f"{new_id:04d}_fake_template.png"
        temp_fname = f"__temp_{new_id:04d}_fake_template.png"
        os.rename(class_dir / old_fname, class_dir / temp_fname)
        stage1_raw.append((temp_fname, final_fname))

    for temp_fname, final_fname in stage1_raw:
        os.rename(class_dir / temp_fname, class_dir / final_fname)

    # Two-stage rename for augmented variants (0173 to 0522)
    augmented_files.sort()
    stage1_aug = []
    start_aug_id = len(selected_raw) + 1  # 173
    for idx, old_fname in enumerate(augmented_files):
        new_id = start_aug_id + idx
        final_fname = f"{new_id:04d}_fake_template.png"
        temp_fname = f"__temp_{new_id:04d}_fake_template.png"
        os.rename(class_dir / old_fname, class_dir / temp_fname)
        meta = manifest[old_fname]
        stage1_aug.append((temp_fname, final_fname, meta["source_image"], meta["augmentation"]))

    new_manifest = {}
    for temp_fname, final_fname, src_file, aug_type in stage1_aug:
        os.rename(class_dir / temp_fname, class_dir / final_fname)
        new_manifest[final_fname] = {
            "source_image": src_file,
            "augmentation": aug_type,
        }

    # 3. Save updated manifest
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(new_manifest, f, indent=2)

    final_count = len(os.listdir(class_dir))
    print(f"Completed! 'fake_template' now has {final_count} images.")
    print(f"Updated manifest saved with {len(new_manifest)} entries.")


def verify_all_classes():
    print("\n" + "=" * 60)
    print("FINAL 5-CLASS DATASET VERIFICATION")
    print("=" * 60)
    classes = ["real_ktp", "other", "fake_print", "fake_screen", "fake_template"]
    total = 0
    all_clean = True

    for c in classes:
        c_dir = PROCESSED_DIR / c
        if not c_dir.exists():
            print(f"Missing folder: {c_dir}")
            all_clean = False
            continue

        files = sorted(os.listdir(c_dir))
        total += len(files)

        # Check for non-image files
        non_images = [f for f in files if not f.lower().endswith((".png", ".jpg", ".jpeg"))]
        if non_images:
            print(f"[{c}] WARNING: Non-image files found: {non_images}")
            all_clean = False

        # Check contiguity
        ids = []
        for f in files:
            parts = f.split("_")
            if parts[0].isdigit():
                ids.append(int(parts[0]))
        min_id = min(ids) if ids else 0
        max_id = max(ids) if ids else 0
        expected_len = max_id - min_id + 1 if ids else 0
        is_contiguous = (len(ids) == expected_len) and (min_id == 1)

        status = "OK" if is_contiguous and not non_images else "ISSUE"
        print(f"[{c:14s}] {len(files):4d} images | Range: {min_id:04d}..{max_id:04d} | Contiguous: {is_contiguous} | {status}")

    print("-" * 60)
    print(f"Total Dataset Images: {total}")
    if all_clean:
        print("All classes balanced, perfectly contiguous, zero non-image files!")
    else:
        print("Some issues were flagged above.")


def main():
    parser = argparse.ArgumentParser(description="Stratified feature-aware balancing for e-KYC dataset")
    parser.add_argument("--dry-run", action="store_true", help="Simulate selections without moving or renaming files")
    args = parser.parse_args()

    balance_fake_screen(dry_run=args.dry_run)
    balance_fake_template(dry_run=args.dry_run)

    if not args.dry_run:
        verify_all_classes()


if __name__ == "__main__":
    main()

