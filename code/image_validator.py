"""Pre-processing image validation: size, format, corruption checks."""

import logging
from pathlib import Path
from typing import Any

from PIL import Image

logger = logging.getLogger("evidence_review.image_validator")

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}


def validate_images(image_paths: list[Path]) -> list[dict[str, Any]]:
    results = []
    for p in image_paths:
        result = {"image_path": str(p), "valid": True, "errors": []}

        if not p.exists():
            result["valid"] = False
            result["errors"].append("File not found")
            results.append(result)
            continue

        ext = p.suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            result["valid"] = False
            result["errors"].append(f"Unsupported extension: {ext}")

        try:
            size = p.stat().st_size
            if size > MAX_FILE_SIZE_BYTES:
                result["valid"] = False
                result["errors"].append(f"File too large: {size} bytes > {MAX_FILE_SIZE_BYTES}")
        except OSError as e:
            result["valid"] = False
            result["errors"].append(f"Cannot stat file: {e}")

        if result["valid"]:
            try:
                img = Image.open(p)
                img.verify()
            except Exception as e:
                result["valid"] = False
                result["errors"].append(f"Corrupt or unreadable: {e}")

        results.append(result)

    return results


def any_valid_images(results: list[dict[str, Any]]) -> bool:
    return any(r["valid"] for r in results)


def all_images_valid(results: list[dict[str, Any]]) -> bool:
    return bool(results) and all(r["valid"] for r in results)
