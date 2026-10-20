"""Regression tests for the second audit pass (2026-10)."""
import json
import sys
import types

import pytest
from PIL import Image

from verifyiq.v2.fraud.image_fraud import ImageFraudDetector
from verifyiq.v2.fraud.metadata_fraud import MetadataFraudDetector

SOFTWARE = 0x0131
MODEL = 0x0110
EXIF_IFD = 0x8769
DATETIME_ORIGINAL = 0x9003


def _photo(path, software, taken, model="iPhone 15"):
    exif = Image.Exif()
    exif[SOFTWARE] = software
    exif[MODEL] = model
    exif.get_ifd(EXIF_IFD)[DATETIME_ORIGINAL] = taken
    Image.new("RGB", (64, 48), (120, 80, 40)).save(path, exif=exif)
    return str(path)


def test_unedited_phone_photos_taken_together_are_not_flagged(tmp_path):
    a = _photo(tmp_path / "a.jpg", "17.4.1", "2026:10:01 12:00:00")
    b = _photo(tmp_path / "b.jpg", "17.4.1", "2026:10:01 12:00:40")
    result = MetadataFraudDetector().check([a, b])
    assert result.flags == []
    assert result.fraud_score == 0.0


def test_editing_software_is_still_flagged(tmp_path):
    a = _photo(tmp_path / "a.jpg", "Adobe Photoshop 25.0 (Windows)", "2026:10:01 12:00:00")
    result = MetadataFraudDetector().check([a])
    assert result.has_editing
    assert "edited_image" in result.flags


def test_photos_days_apart_are_flagged(tmp_path):
    a = _photo(tmp_path / "a.jpg", "17.4.1", "2026:10:01 12:00:00")
    b = _photo(tmp_path / "b.jpg", "17.4.1", "2026:10:05 12:00:00")
    result = MetadataFraudDetector().check([a, b])
    assert result.timestamp_mismatch
    assert "timestamp_mismatch" in result.flags


def test_screenshot_detection_uses_uniform_top_row(tmp_path):
    shot = Image.new("RGB", (1600, 900), (255, 255, 255))
    shot.paste((10, 200, 30), (0, 5, 1600, 900))
    shot.save(tmp_path / "shot.png")
    photo = Image.effect_noise((1600, 900), 64).convert("RGB")
    photo.save(tmp_path / "photo.png")
    detector = ImageFraudDetector(cache_dir=str(tmp_path / "cache"))
    assert detector._is_screenshot(str(tmp_path / "shot.png"))
    assert not detector._is_screenshot(str(tmp_path / "photo.png"))


class _FakeModels:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def generate_content(self, model, contents, config):
        self.calls.append(contents)
        return types.SimpleNamespace(text=self.reply)


def _install_fake_genai(monkeypatch, reply):
    models = _FakeModels(reply)
    genai = types.ModuleType("google.genai")
    genai.Client = lambda api_key: types.SimpleNamespace(models=models)
    google = types.ModuleType("google")
    google.genai = genai
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.genai", genai)
    return models


def test_gemini_provider_sends_prompt_and_aligns_assessments(tmp_path, monkeypatch):
    from verifyiq.v2.providers.gemini_provider import GeminiProvider

    good = tmp_path / "good.jpg"
    Image.new("RGB", (32, 32)).save(good)
    missing = tmp_path / "missing.jpg"
    reply = json.dumps({"per_image_assessments": [
        {"damage_visible": "true", "damage_type": "dent", "object_part": "door", "confidence": 0.9,
         "is_clear": True, "angle_sufficient": True, "lighting_adequate": True},
    ]})
    models = _install_fake_genai(monkeypatch, reply)

    report = GeminiProvider(config={"api_key": "test"}).analyze(
        [str(missing), str(good)], "dent on my door", "car")

    prompt = models.calls[0][0]
    assert isinstance(prompt, str)
    assert "per_image_assessments" in prompt
    assert "dent on my door" in prompt
    assessments = report.observations[0].assessments
    assert [a.image_path for a in assessments] == [str(good)]
    assert assessments[0].damage_visible is True


@pytest.fixture
def api_client(monkeypatch):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    import api.main as main

    class _Decision:
        claim_status = "supported"
        confidence = 0.9
        severity = "low"
        risk_flags = []
        justification = "ok"

    class _Pipeline:
        vision_manager = types.SimpleNamespace(
            state=types.SimpleNamespace(value="available"),
            mode=types.SimpleNamespace(value="demo"),
            get_health_report=lambda: {},
        )

        def process(self, **kwargs):
            return _Decision()

    monkeypatch.setattr(main, "_pipeline", _Pipeline())
    monkeypatch.delenv("VERIFYIQ_API_KEY", raising=False)
    with TestClient(main.app) as client:
        yield client


CLAIM = {"claim_text": "scratch", "claim_object": "car"}


def test_api_is_open_when_no_key_configured(api_client):
    assert api_client.post("/claim", json=CLAIM).status_code == 200


def test_api_requires_key_when_configured(api_client, monkeypatch):
    monkeypatch.setenv("VERIFYIQ_API_KEY", "s3cret")
    assert api_client.post("/claim", json=CLAIM).status_code == 401
    assert api_client.post("/claim", json=CLAIM, headers={"X-API-Key": "wrong"}).status_code == 401
    assert api_client.post("/claim", json=CLAIM, headers={"X-API-Key": "s3cret"}).status_code == 200
    assert api_client.get("/metrics").status_code == 401
    assert api_client.get("/health").status_code == 200


def test_api_rejects_oversized_batch(api_client):
    from api.main import MAX_BATCH_CLAIMS

    body = {"claims": [CLAIM] * (MAX_BATCH_CLAIMS + 1)}
    assert api_client.post("/batch", json=body).status_code == 422
    assert api_client.post("/batch", json={"claims": [CLAIM] * 2}).status_code == 200
