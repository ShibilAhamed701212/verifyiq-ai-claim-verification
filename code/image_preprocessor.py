"""
Image format normalization pipeline.

Converts all input images to standard JPEG before feeding to downstream
modules (OCR, CV detectors, Gemini vision). Handles AVIF, PNG, WebP,
BMP, and any other format PIL can open.
"""

import logging
import tempfile
from pathlib import Path

from PIL import Image

logger = logging.getLogger("evidence_review.preprocessor")

_cleanup_dirs: list[Path] = []


def normalize_images(image_paths: list[Path]) -> list[Path]:
    """Convert non-JPEG images to JPEG. Returns paths (original or converted)."""
    out: list[Path] = []
    temp_dir = None

    for p in image_paths:
        if not p.exists():
            out.append(p)
            continue

        try:
            img = Image.open(p)
            if img.format == "JPEG":
                out.append(p)
                continue

            if temp_dir is None:
                temp_dir = Path(tempfile.mkdtemp(prefix="verifyiq_"))
                _cleanup_dirs.append(temp_dir)

            rgb = img.convert("RGB") if img.mode in ("RGBA", "LA", "P") else img
            dst = temp_dir / f"{p.stem}.jpg"
            rgb.save(dst, "JPEG", quality=95)
            logger.info(f"Converted {p.name} ({img.format}) -> {dst.name}")
            out.append(dst)

        except Exception as e:
            logger.warning(f"Failed to normalize {p}: {e}")
            out.append(p)

    return out
