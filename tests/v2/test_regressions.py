"""Regression tests for bugs fixed during the 2026-10 engineering audit."""
import subprocess
import sys
from pathlib import Path

from verifyiq.v2.explainability.tracer import DecisionTracer
from verifyiq.v2.models.confidence import ConfidenceBreakdown, ConfidenceReport
from verifyiq.v2.models.consensus import ConsensusReport
from verifyiq.v2.models.conversation import ConversationReport
from verifyiq.v2.models.decision import V2Decision
from verifyiq.v2.models.evidence import EvidenceReport
from verifyiq.v2.models.fraud import FraudReport
from verifyiq.v2.pipeline import V2Pipeline
from verifyiq.v2.security.sanitizer import InputSanitizer

ROOT = Path(__file__).resolve().parents[2]


def test_sanitizer_rejects_sibling_directory_with_shared_prefix(tmp_path):
    base = tmp_path / "images"
    sibling = tmp_path / "images-private"
    base.mkdir()
    sibling.mkdir()
    (sibling / "secret.jpg").write_bytes(b"x")
    assert InputSanitizer.sanitize_image_path(str(sibling / "secret.jpg"), str(base)) == ""


def test_sanitizer_accepts_path_inside_base(tmp_path):
    (tmp_path / "a.jpg").write_bytes(b"x")
    result = InputSanitizer.sanitize_image_path("a.jpg", str(tmp_path))
    assert result == str((tmp_path / "a.jpg").resolve())


def _trace(status):
    decision = V2Decision(claim_status=status, evidence_standard_met=False)
    return DecisionTracer().trace(
        decision,
        ConsensusReport(agreement_score=0.0, confidence=0.0, uncertainty=1.0, models_used=0, models_succeeded=0),
        FraudReport(),
        ConversationReport(),
        EvidenceReport(evidence_standard_met=False, reason="No images were submitted."),
        ConfidenceReport(final_confidence=0.2, routing="evidence_request", breakdown=ConfidenceBreakdown()),
    )


def test_not_enough_information_is_not_labelled_contradicted():
    result = _trace("not_enough_information")
    assert "Contradicted because" not in result.justification
    assert result.justification.startswith("Not supported because")


def test_contradicted_keeps_contradicted_label():
    assert _trace("contradicted").justification.startswith("Contradicted because")


def test_fraud_layer_passes_parsed_damage_type_to_behavioral_detector():
    pipeline = V2Pipeline(config={"providers": {}})
    seen = {}

    def fake_check(user_id, damage_type, images):
        seen["damage_type"] = damage_type
        from verifyiq.v2.models.fraud import BehavioralFraudResult
        return BehavioralFraudResult()

    pipeline.behavioral_fraud.check = fake_check
    pipeline._run_fraud([], "u1", "Customer: there is a deep dent on the door")
    assert seen["damage_type"] == "dent"


def test_v2_pipeline_imports_when_stdlib_code_is_already_loaded(tmp_path):
    # Simulates an installed package: the project root is on sys.path *after*
    # the stdlib, and the stdlib ``code`` module has already been imported.
    script = (
        "import code, sys; "
        f"sys.path.append({str(ROOT)!r}); "
        "from verifyiq.v2.pipeline import V2Pipeline; import verifyiq.v1; print('ok')"
    )
    proc = subprocess.run([sys.executable, "-c", script], cwd=tmp_path, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "ok"
