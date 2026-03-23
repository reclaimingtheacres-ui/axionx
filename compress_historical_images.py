#!/usr/bin/env python3
"""
One-off historical image compression migration for AxionX.

Walks the uploads directory tree, finds image files, and compresses them
in-place using Pillow (max 1600px, JPEG quality 72, EXIF orientation preserved).

Usage:
    # Dry run (report only, no changes)
    python3 compress_historical_images.py --dry-run

    # Live run (compress in-place)
    python3 compress_historical_images.py

    # Process in batches of N
    python3 compress_historical_images.py --batch-size 50

    # Custom upload directory
    python3 compress_historical_images.py --uploads-dir /home/site/data/uploads

    # Skip PNGs (default: PNGs are skipped)
    python3 compress_historical_images.py --include-png

    # Set size threshold (skip files already below this size in KB)
    python3 compress_historical_images.py --threshold-kb 200
"""

import argparse
import csv
import io
import logging
import mimetypes
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError:
    print("ERROR: Pillow is required. Install with: pip install Pillow")
    sys.exit(1)

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIF_SUPPORT = True
except ImportError:
    HEIF_SUPPORT = False

MAX_DIM = 1600
JPEG_QUALITY = 72
THRESHOLD_KB = 200

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.heic', '.heif', '.webp', '.bmp', '.tiff', '.tif'}
SKIP_EXTENSIONS = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.csv', '.txt', '.zip', '.mp3', '.wav', '.m4a'}

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"


def detect_image_type(filepath):
    try:
        with Image.open(filepath) as img:
            return img.format
    except Exception:
        return None


def should_process(filepath, include_png, threshold_bytes):
    ext = Path(filepath).suffix.lower()
    if ext in SKIP_EXTENSIONS:
        return False, "non-image extension"

    if ext not in IMAGE_EXTENSIONS:
        fmt = detect_image_type(filepath)
        if not fmt:
            return False, "not an image file"
    else:
        fmt = None

    if ext in ('.heic', '.heif') and not HEIF_SUPPORT:
        return False, "HEIC/HEIF not supported (pillow-heif not installed)"

    if ext == '.png' and not include_png:
        return False, "PNG skipped (use --include-png to process)"

    size = os.path.getsize(filepath)
    if size < threshold_bytes:
        return False, f"below threshold ({size:,} bytes < {threshold_bytes:,})"

    return True, "eligible"


def compress_image(filepath, dry_run=False, db_conn=None):
    original_size = os.path.getsize(filepath)
    ext = Path(filepath).suffix.lower()

    try:
        img = Image.open(filepath)
    except Exception as e:
        return {
            "status": "error",
            "error": f"cannot open: {e}",
            "original_size": original_size,
            "new_size": original_size,
            "saved": 0,
        }

    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    w, h = img.size
    original_dims = f"{w}x{h}"

    if w > MAX_DIM or h > MAX_DIM:
        ratio = min(MAX_DIM / w, MAX_DIM / h)
        new_w = int(w * ratio)
        new_h = int(h * ratio)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        new_dims = f"{new_w}x{new_h}"
    else:
        new_dims = original_dims

    if img.mode in ('RGBA', 'LA', 'P'):
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        background.paste(img, mask=img.split()[-1] if 'A' in img.mode else None)
        img = background
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=JPEG_QUALITY, optimize=True, progressive=True)
    new_size = buf.tell()

    if new_size >= original_size:
        return {
            "status": "skipped_no_savings",
            "original_size": original_size,
            "new_size": original_size,
            "saved": 0,
            "original_dims": original_dims,
            "new_dims": new_dims,
        }

    needs_rename = ext not in ('.jpg', '.jpeg')
    if needs_rename:
        new_filepath = str(Path(filepath).with_suffix('.jpg'))
    else:
        new_filepath = filepath

    if not dry_run:
        tmp_path = filepath + ".tmp_compress"
        try:
            buf.seek(0)
            with open(tmp_path, 'wb') as f:
                f.write(buf.read())
            shutil.move(tmp_path, new_filepath)
            if needs_rename and os.path.exists(filepath) and filepath != new_filepath:
                os.remove(filepath)
            if needs_rename and db_conn:
                _update_db_references(db_conn, filepath, new_filepath)
        except Exception as e:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            return {
                "status": "error",
                "error": f"write failed: {e}",
                "original_size": original_size,
                "new_size": original_size,
                "saved": 0,
            }

    saved = original_size - new_size
    pct = (saved / original_size * 100) if original_size > 0 else 0

    result = {
        "status": "compressed" if not dry_run else "would_compress",
        "original_size": original_size,
        "new_size": new_size,
        "saved": saved,
        "pct_saved": round(pct, 1),
        "original_dims": original_dims,
        "new_dims": new_dims,
    }
    if needs_rename:
        result["renamed_to"] = os.path.basename(new_filepath)
    return result


def _update_db_references(conn, old_filepath, new_filepath):
    old_basename = os.path.basename(old_filepath)
    new_basename = os.path.basename(new_filepath)

    old_rel = old_basename
    new_rel = new_basename

    tables_cols = [
        ("job_note_files", "filepath", None),
        ("job_note_files", "filename", None),
        ("job_documents", "stored_filename", None),
        ("customers", "id_image_path", None),
        ("customers", "id_image_filename", None),
    ]

    cursor = conn.cursor()
    for table, col, _ in tables_cols:
        try:
            cursor.execute(
                f"UPDATE {table} SET {col} = REPLACE({col}, ?, ?) WHERE {col} LIKE ?",
                (old_rel, new_rel, f"%{old_rel}%")
            )
            if cursor.rowcount > 0:
                logging.getLogger("compress_migration").info(
                    f"  DB updated: {table}.{col} — {cursor.rowcount} row(s) "
                    f"'{old_rel}' -> '{new_rel}'"
                )
        except Exception as e:
            logging.getLogger("compress_migration").warning(
                f"  DB update failed for {table}.{col}: {e}"
            )
    conn.commit()


def format_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"


def run_migration(uploads_dir, dry_run, include_png, threshold_kb, batch_size, db_path=None):
    threshold_bytes = threshold_kb * 1024

    db_conn = None
    if not dry_run and db_path and os.path.isfile(db_path):
        import sqlite3
        db_conn = sqlite3.connect(db_path)
        db_conn.row_factory = sqlite3.Row

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    mode_label = "dryrun" if dry_run else "live"
    log_filename = f"compress_migration_{mode_label}_{timestamp}.log"
    csv_filename = f"compress_migration_{mode_label}_{timestamp}.csv"

    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=[
            logging.FileHandler(log_filename),
            logging.StreamHandler(sys.stdout),
        ]
    )
    logger = logging.getLogger("compress_migration")

    logger.info("=" * 70)
    logger.info("AxionX Historical Image Compression Migration")
    logger.info("=" * 70)
    logger.info(f"Mode:           {'DRY RUN (no changes)' if dry_run else 'LIVE (compressing in-place)'}")
    logger.info(f"Uploads dir:    {uploads_dir}")
    logger.info(f"Max dimension:  {MAX_DIM}px")
    logger.info(f"JPEG quality:   {JPEG_QUALITY}")
    logger.info(f"Size threshold: {threshold_kb} KB")
    logger.info(f"Include PNGs:   {include_png}")
    logger.info(f"Batch size:     {batch_size or 'unlimited'}")
    logger.info(f"HEIF support:   {HEIF_SUPPORT}")
    logger.info("=" * 70)

    if not dry_run:
        logger.warning("LIVE MODE — files will be overwritten in-place!")
        logger.warning("Ensure you have a backup before proceeding.")

    if not os.path.isdir(uploads_dir):
        logger.error(f"Uploads directory does not exist: {uploads_dir}")
        return

    all_files = []
    for root, dirs, files in os.walk(uploads_dir):
        for fname in sorted(files):
            fpath = os.path.join(root, fname)
            if os.path.isfile(fpath):
                all_files.append(fpath)

    logger.info(f"Found {len(all_files)} total files in {uploads_dir}")

    eligible = []
    skipped_reasons = {}
    for fpath in all_files:
        ok, reason = should_process(fpath, include_png, threshold_bytes)
        if ok:
            eligible.append(fpath)
        else:
            skipped_reasons[reason] = skipped_reasons.get(reason, 0) + 1

    logger.info(f"Eligible for compression: {len(eligible)}")
    for reason, count in sorted(skipped_reasons.items()):
        logger.info(f"  Skipped ({reason}): {count}")

    if not eligible:
        logger.info("No files to process. Exiting.")
        return

    if batch_size and batch_size > 0:
        eligible = eligible[:batch_size]
        logger.info(f"Processing batch of {len(eligible)} files")

    results = []
    total_original = 0
    total_new = 0
    total_saved = 0
    compressed_count = 0
    skipped_count = 0
    error_count = 0

    csv_file = open(csv_filename, 'w', newline='')
    writer = csv.writer(csv_file)
    writer.writerow([
        "file_path", "status", "original_size_bytes", "new_size_bytes",
        "saved_bytes", "pct_saved", "original_dims", "new_dims", "renamed_to", "error"
    ])

    for i, fpath in enumerate(eligible, 1):
        rel_path = os.path.relpath(fpath, uploads_dir)
        logger.info(f"[{i}/{len(eligible)}] Processing: {rel_path}")

        result = compress_image(fpath, dry_run=dry_run, db_conn=db_conn)
        status = result["status"]

        total_original += result["original_size"]

        if status in ("compressed", "would_compress"):
            compressed_count += 1
            total_new += result["new_size"]
            total_saved += result["saved"]
            rename_note = f" -> {result['renamed_to']}" if result.get("renamed_to") else ""
            logger.info(
                f"  {status}: {format_size(result['original_size'])} -> "
                f"{format_size(result['new_size'])} "
                f"(-{result['pct_saved']}%) "
                f"{result.get('original_dims', '?')} -> {result.get('new_dims', '?')}"
                f"{rename_note}"
            )
        elif status == "skipped_no_savings":
            skipped_count += 1
            total_new += result["original_size"]
            logger.info(f"  skipped: recompression would not reduce size")
        elif status == "error":
            error_count += 1
            total_new += result["original_size"]
            logger.error(f"  ERROR: {result.get('error', 'unknown')}")

        writer.writerow([
            rel_path,
            status,
            result["original_size"],
            result["new_size"],
            result.get("saved", 0),
            result.get("pct_saved", 0),
            result.get("original_dims", ""),
            result.get("new_dims", ""),
            result.get("renamed_to", ""),
            result.get("error", ""),
        ])

    csv_file.close()

    logger.info("")
    logger.info("=" * 70)
    logger.info("SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Files scanned:              {len(all_files)}")
    logger.info(f"Files eligible:             {len(eligible)}")
    logger.info(f"{'Would compress' if dry_run else 'Compressed'}:    {compressed_count}")
    logger.info(f"Skipped (no savings):       {skipped_count}")
    logger.info(f"Errors:                     {error_count}")
    logger.info(f"Total original size:        {format_size(total_original)}")
    logger.info(f"Total new size:             {format_size(total_new)}")
    logger.info(f"Total saved:                {format_size(total_saved)}")
    if total_original > 0:
        logger.info(f"Overall reduction:          {total_saved / total_original * 100:.1f}%")
    logger.info(f"Report CSV:                 {csv_filename}")
    logger.info(f"Log file:                   {log_filename}")
    logger.info("=" * 70)

    if db_conn:
        db_conn.close()


def main():
    db_path = os.getenv("DB_PATH", "axion.db")
    default_uploads = os.path.join(os.path.dirname(os.path.abspath(db_path)), "uploads")

    parser = argparse.ArgumentParser(
        description="AxionX Historical Image Compression Migration"
    )
    parser.add_argument(
        "--dry-run", action="store_true", default=False,
        help="Report expected savings without making changes"
    )
    parser.add_argument(
        "--uploads-dir", type=str, default=default_uploads,
        help=f"Path to uploads directory (default: {default_uploads})"
    )
    parser.add_argument(
        "--include-png", action="store_true", default=False,
        help="Include PNG files (skipped by default)"
    )
    parser.add_argument(
        "--threshold-kb", type=int, default=THRESHOLD_KB,
        help=f"Skip files below this size in KB (default: {THRESHOLD_KB})"
    )
    parser.add_argument(
        "--batch-size", type=int, default=None,
        help="Process only N files per run (for Azure timeout safety)"
    )
    args = parser.parse_args()

    run_migration(
        uploads_dir=args.uploads_dir,
        dry_run=args.dry_run,
        include_png=args.include_png,
        threshold_kb=args.threshold_kb,
        batch_size=args.batch_size,
        db_path=db_path,
    )


if __name__ == "__main__":
    main()
