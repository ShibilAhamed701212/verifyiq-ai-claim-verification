"""Regression: the OCR check must not hard-code the Windows Tesseract path."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "code"))
from cv import text_detector


def test_env_override_wins(monkeypatch):
    monkeypatch.setenv("TESSERACT_CMD", "/opt/tesseract/bin/tesseract")
    assert text_detector._tesseract_cmd() == "/opt/tesseract/bin/tesseract"


def test_falls_back_to_path_lookup_when_windows_default_missing(monkeypatch):
    monkeypatch.delenv("TESSERACT_CMD", raising=False)
    monkeypatch.setattr(text_detector, "_WINDOWS_DEFAULT_CMD", "/nonexistent/tesseract.exe")
    assert text_detector._tesseract_cmd() is None
