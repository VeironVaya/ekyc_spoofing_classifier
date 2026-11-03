#!/usr/bin/env python3
"""
Direct Resumable Downloader for Indonesian KTP Dummy Dataset (24K Flat Subset)
Repository: cloverx-id/indonesian-id-card-dummy
Target: data/flat/train-00000-of-00012.parquet to train-00011-of-00012.parquet (~11.8 GB total)
"""

import argparse
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
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

try:
    import pyarrow.parquet as pq
except ImportError:
    pq = None

BASE_URL = "https://huggingface.co/datasets/cloverx-id/indonesian-id-card-dummy/resolve/main"
TOTAL_PARTITIONS = 12
CHUNK_SIZE = 1024 * 1024  # 1 MB chunk


def check_disk_space(target_dir: Path, required_gb: float) -> bool:
    """Check if target drive has enough free disk space."""
    total, used, free = shutil.disk_usage(target_dir.anchor or ".")
    free_gb = free / (1024**3)
    print(f"📊 Disk space on {target_dir.anchor or '.'}: {free_gb:.1f} GB free (Required: ~{required_gb:.1f} GB)")
    if free_gb < required_gb:
        print(f"⚠️ Warning: Low disk space! Free: {free_gb:.1f} GB, Required: ~{required_gb:.1f} GB")
        return False
    return True


def verify_partition(file_path: Path):
    """Verify that the downloaded parquet file is readable and count rows."""
    if pq is None:
        return
    try:
        parquet_file = pq.ParquetFile(file_path)
        metadata = parquet_file.metadata
        print(f"   ✅ Verified: {metadata.num_rows:,} rows | {metadata.num_columns} columns | {file_path.stat().st_size / (1024*1024):.1f} MB")
    except Exception as exc:
        print(f"   ❌ Verification failed for {file_path.name}: {exc}")


def download_file_with_resume(url: str, final_path: Path, token: str = None) -> bool:
    """Download a file with HTTP Range resume support."""
    part_path = final_path.with_suffix(final_path.suffix + ".part")
    existing_bytes = part_path.stat().st_size if part_path.exists() else 0

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # Get total file size via HEAD request
    head_req = urllib.request.Request(url, headers=headers, method="HEAD")
    try:
        with urllib.request.urlopen(head_req, timeout=30) as resp:
            total_size = int(resp.headers.get("Content-Length", 0))
    except Exception as exc:
        print(f"   ❌ Failed to query file size: {exc}")
        return False

    if existing_bytes > 0:
        if existing_bytes == total_size:
            part_path.rename(final_path)
            print(f"   ⏩ Already completely downloaded in .part. Promoted to {final_path.name}.")
            return True
        elif existing_bytes < total_size:
            print(f"   🔄 Resuming download from {existing_bytes / (1024*1024):.1f} MB / {total_size / (1024*1024):.1f} MB...")
            headers["Range"] = f"bytes={existing_bytes}-"
        else:
            # File is larger than remote? reset
            existing_bytes = 0

    req = urllib.request.Request(url, headers=headers)
    mode = "ab" if existing_bytes > 0 else "wb"

    try:
        with urllib.request.urlopen(req, timeout=60) as resp, open(part_path, mode) as f:
            if tqdm is not None:
                pbar = tqdm(
                    total=total_size,
                    initial=existing_bytes,
                    unit="B",
                    unit_scale=True,
                    unit_divisor=1024,
                    desc=final_path.name,
                    leave=True,
                )
            else:
                pbar = None

            downloaded = existing_bytes
            last_report = time.time()

            while True:
                chunk = resp.read(CHUNK_SIZE)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if pbar:
                    pbar.update(len(chunk))
                else:
                    if time.time() - last_report > 5:
                        print(f"   ⬇️ {downloaded / (1024*1024):.1f} MB / {total_size / (1024*1024):.1f} MB ({(downloaded/total_size)*100:.1f}%)")
                        last_report = time.time()

            if pbar:
                pbar.close()

        # Rename .part to .parquet on completion
        if final_path.exists():
            final_path.unlink()
        part_path.rename(final_path)
        print(f"   💾 Successfully saved: {final_path.name} ({final_path.stat().st_size / (1024*1024):.1f} MB)")
        return True

    except Exception as exc:
        print(f"   ❌ Network error during download: {exc}")
        print(f"   (Partial file saved at {part_path.name} - run script again to resume)")
        return False


def main():
    parser = argparse.ArgumentParser(description="Download Indonesian KTP Dummy Dataset (Flat Subset)")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="datasets/raw/cloverx_ktp/flat",
        help="Directory where parquet partitions will be saved (default: datasets/raw/cloverx_ktp/flat)",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=0,
        help="Index of first partition to download (0-11, default: 0)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of partitions to download (default: all remaining partitions)",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=os.getenv("HF_TOKEN", None),
        help="Hugging Face personal access token (optional, reads from HF_TOKEN env var)",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip PyArrow integrity verification after download",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List files and show storage requirements without downloading",
    )

    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    start_idx = max(0, min(args.start, TOTAL_PARTITIONS - 1))
    count = TOTAL_PARTITIONS - start_idx
    if args.limit is not None and args.limit > 0:
        count = min(count, args.limit)
    end_idx = start_idx + count

    partitions = [
        f"data/flat/train-{i:05d}-of-{TOTAL_PARTITIONS:05d}.parquet"
        for i in range(start_idx, end_idx)
    ]

    estimated_total_gb = (count * 990) / 1024

    print("=" * 70)
    print("🇮🇩 INDONESIAN KTP DUMMY DATASET DOWNLOADER (24K FLAT SUBSET)")
    print("=" * 70)
    print(f"Source Base: {BASE_URL}")
    print(f"Destination: {output_dir}")
    print(f"Partitions : {count} file(s) [indices {start_idx} to {end_idx - 1} of {TOTAL_PARTITIONS}]")
    print(f"Est. Size  : ~{estimated_total_gb:.2f} GB")
    print("=" * 70)

    if not check_disk_space(output_dir, estimated_total_gb):
        if not args.dry_run:
            proceed = input("Proceed anyway? (y/N): ").strip().lower()
            if proceed != "y":
                print("Download cancelled.")
                return

    if args.dry_run:
        print("\n[DRY RUN] Partitions that would be downloaded:")
        for p in partitions:
            print(f"  - {p} (~990 MB)")
        print("\nDry run complete. No files were downloaded.")
        return

    start_time = time.time()
    downloaded_files = []

    for idx, remote_rel in enumerate(partitions, 1):
        filename = Path(remote_rel).name
        target_file = output_dir / filename
        url = f"{BASE_URL}/{remote_rel}"

        print(f"\n[{idx}/{count}] Processing {filename}...")

        if target_file.exists() and target_file.stat().st_size > 10 * 1024 * 1024:
            print(f"   ⏩ Already exists ({target_file.stat().st_size / (1024*1024):.1f} MB). Skipping.")
            if not args.no_verify:
                verify_partition(target_file)
            downloaded_files.append(target_file)
            continue

        success = download_file_with_resume(url, target_file, token=args.token)
        if success:
            if not args.no_verify:
                verify_partition(target_file)
            downloaded_files.append(target_file)
        else:
            print("   ⚠️ Stopping download loop due to failure.")
            break

    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print("DOWNLOAD RUN SUMMARY")
    print("=" * 70)
    print(f"Files ready/verified : {len(downloaded_files)} / {count}")
    print(f"Total time elapsed   : {elapsed / 60:.1f} minutes")
    print(f"Target folder        : {output_dir}")

    total_rows = 0
    if pq is not None:
        for f in downloaded_files:
            try:
                total_rows += pq.ParquetFile(f).metadata.num_rows
            except Exception:
                pass
        if total_rows > 0:
            print(f"Total verified KTP records: {total_rows:,} cards")
    print("=" * 70)


if __name__ == "__main__":
    main()
