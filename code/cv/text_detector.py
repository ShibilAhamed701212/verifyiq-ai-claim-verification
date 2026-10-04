"""OCR text detector using pytesseract with safe-mode fallback."""

import logging
import os
from pathlib import Path

logger = logging.getLogger("evidence_review.text_detector")

_TESSERACT_AVAILABLE: bool | None = None
_WINDOWS_DEFAULT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def _tesseract_cmd() -> str | None:
    """Tesseract binary to use: $TESSERACT_CMD, else the Windows default
    install path if it exists, else None (pytesseract then searches PATH)."""
    env_cmd = os.environ.get("TESSERACT_CMD")
    if env_cmd:
        return env_cmd
    if Path(_WINDOWS_DEFAULT_CMD).exists():
        return _WINDOWS_DEFAULT_CMD
    return None


def _check_tesseract() -> bool:
    global _TESSERACT_AVAILABLE
    if _TESSERACT_AVAILABLE is not None:
        return _TESSERACT_AVAILABLE
    try:
        import pytesseract
        cmd = _tesseract_cmd()
        if cmd:
            pytesseract.pytesseract.tesseract_cmd = cmd
        pytesseract.get_tesseract_version()
        _TESSERACT_AVAILABLE = True
    except Exception as e:
        logger.warning(f"Tesseract not available, OCR disabled: {e}")
        _TESSERACT_AVAILABLE = False
    return _TESSERACT_AVAILABLE


class TextDetector:
    """Detects text in images using Tesseract OCR (safe fallback if unavailable)."""

    def __init__(self, min_text_length: int = 3, confidence_threshold: int = 30):
        self.min_text_length = min_text_length
        self.confidence_threshold = confidence_threshold
        self.available = _check_tesseract()
        self._pytesseract = None
        if self.available:
            import pytesseract
            self._pytesseract = pytesseract

    def contains_text(self, image_path: Path) -> bool:
        if not self.available or self._pytesseract is None:
            return False
        if not image_path.exists():
            return False
        try:
            data = self._pytesseract.image_to_data(str(image_path), output_type=self._pytesseract.Output.DICT)
            for i, conf in enumerate(data["conf"]):
                try:
                    conf_val = int(conf)
                except (ValueError, TypeError):
                    continue
                text = (data["text"][i] or "").strip()
                if conf_val > self.confidence_threshold and len(text) >= self.min_text_length:
                    return True
        except Exception as e:
            logger.warning(f"OCR failed for {image_path}: {e}")
        return False

    def has_text_images(self, image_paths: list) -> list:
        results = []
        for p in image_paths:
            results.append({
                "image_id": p.stem,
                "contains_text": self.contains_text(p),
            })
        return results
