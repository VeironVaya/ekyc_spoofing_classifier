#!/usr/bin/env python3
"""
Ultra-fast direct PNG dumper for Indonesian KTP Parquet files.
Writes raw PNG bytes directly to disk without decompression overhead.
"""

import argparse
import sys
import time
from pathlib import Path
import pandas as pd

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None


def main():
    parser = argparse.ArgumentParser(description="Dump KTP PNG images from Parquet files")
    parser.add_argument(
        "--input-dir",
        type=str,
        default="datasets/raw/cloverx_ktp/flat",
        help="Directory containing .parquet files (default: datasets/raw/cloverx_ktp/flat)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="datasets/processed/fake_template",
        help="Destination directory for extracted PNGs (default: datasets/processed/fake_template)",
    )
    parser.add_argument(
        "--num",
        type=int,
        default=None,
        help="Number of images to extract (default: all images in parquet files)",
    )

    args = parser.parse_args()

    input_dir = Path(args.input_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    parquet_files = sorted(input_dir.glob("*.parquet"))
    if not parquet_files:
        print(f"❌ No .parquet files found in {input_dir}")
        return

    print("=" * 70)
    print("🚀 FAST KTP IMAGE DUMPER -> FAKE_TEMPLATE")
    print("=" * 70)
    print(f"Input Directory : {input_dir}")
    print(f"Target Directory: {output_dir}")
    print(f"Parquet Files   : {len(parquet_files)} file(s)")
    print("=" * 70)

    total_dumped = 0
    start_time = time.time()

    for pf in parquet_files:
        print(f"\n📂 Reading {pf.name}...")
        df = pd.read_parquet(pf, columns=["image", "nik", "nama"])
        total_rows = len(df)
        print(f"   Found {total_rows:,} records in {pf.name}. Writing PNGs to disk...")

        limit = total_rows if args.num is None else min(total_rows, args.num - total_dumped)
        iterable = range(limit)
        if tqdm is not None:
            iterable = tqdm(iterable, desc=f"Writing {pf.stem}", unit="img")

        for i in iterable:
            row = df.iloc[i]
            nik = str(row.get("nik", f"id_{i}"))
            nama = str(row.get("nama", "unnamed")).strip().replace(" ", "_").replace("/", "_").replace("\\", "_")

            img_data = row["image"]
            raw_bytes = img_data["bytes"] if isinstance(img_data, dict) and "bytes" in img_data else img_data

            filename = f"{nik}_{nama}.png"
            target_path = output_dir / filename

            # Write raw PNG bytes directly
            with open(target_path, "wb") as f:
                f.write(raw_bytes)

            total_dumped += 1
            if args.num is not None and total_dumped >= args.num:
                break

        if args.num is not None and total_dumped >= args.num:
            break

    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print(f"🎉 Complete! Dumped {total_dumped:,} images to: {output_dir}")
    print(f"⏱️ Time taken: {elapsed:.2f} seconds ({total_dumped / max(1, elapsed):.1f} img/s)")
    print("=" * 70)


if __name__ == "__main__":
    main()
