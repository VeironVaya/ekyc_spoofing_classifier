#!/usr/bin/env python3
"""
Utility script to rename dataset files in datasets/processed/ to standardized format:
  <id>_<class_name>.<ext>
Example:
  0001_real_ktp.jpeg
  0001_fake_screen.jpeg
  0001_fake_print.jpeg
  0001_fake_template.png
  0001_other.jpeg
"""

import argparse
import sys
import uuid
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def rename_folder_files(folder_path: Path, class_name: str, dry_run: bool = False):
    if not folder_path.exists():
        print(f"⚠️ Folder not found: {folder_path}")
        return 0

    files = sorted([f for f in folder_path.iterdir() if f.is_file()])
    if not files:
        print(f"ℹ️ No files in {folder_path.name}/")
        return 0

    print(f"\n📂 Renaming {len(files)} files in: {folder_path.name}/ (class: {class_name})")

    # Phase 1: Plan target names
    rename_plan = []
    for i, file_path in enumerate(files, 1):
        ext = file_path.suffix.lower()
        new_name = f"{i:04d}_{class_name}{ext}"
        new_path = folder_path / new_name
        rename_plan.append((file_path, new_path))

    if dry_run:
        print("   [DRY RUN] Preview first 5 renames:")
        for old, new in rename_plan[:5]:
            print(f"   {old.name} -> {new.name}")
        return len(files)

    # Phase 2: Safe two-step rename using temporary filenames to prevent collision
    temp_plan = []
    for old_path, new_path in rename_plan:
        temp_name = f"__tmp_{uuid.uuid4().hex[:8]}__{old_path.name}"
        temp_path = folder_path / temp_name
        old_path.rename(temp_path)
        temp_plan.append((temp_path, new_path))

    # Phase 3: Rename from temp to final standardized name
    for temp_path, final_path in temp_plan:
        if final_path.exists():
            final_path.unlink()
        temp_path.rename(final_path)

    print(f"   ✅ Successfully renamed {len(rename_plan)} files (0001_{class_name} to {len(rename_plan):04d}_{class_name})")
    return len(rename_plan)


def main():
    parser = argparse.ArgumentParser(description="Standardize dataset image names to <id>_<class>.<ext>")
    parser.add_argument(
        "--base-dir",
        type=str,
        default="datasets/processed",
        help="Base directory containing class folders (default: datasets/processed)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview renaming plan without modifying files",
    )

    args = parser.parse_args()
    base_dir = Path(args.base_dir).resolve()

    classes = ["real_ktp", "fake_screen", "fake_print", "fake_template", "other"]

    print("=" * 70)
    print("🏷️ DATASET IMAGE STANDARDIZATION & RENAMING")
    print("=" * 70)
    print(f"Target Directory: {base_dir}")
    print(f"Format Pattern  : <id>_<class>.<ext> (e.g. 0001_fake_screen.jpeg)")
    print(f"Classes Target  : {', '.join(classes)}")
    print("=" * 70)

    total_renamed = 0
    for c in classes:
        folder = base_dir / c
        total_renamed += rename_folder_files(folder, c, dry_run=args.dry_run)

    print("\n" + "=" * 70)
    action = "Planned" if args.dry_run else "Renamed"
    print(f"🎉 Complete! {action} {total_renamed:,} files across {len(classes)} classes.")
    print("=" * 70)


if __name__ == "__main__":
    main()

