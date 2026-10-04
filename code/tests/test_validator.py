"""Tests for output_validator consistency checks."""

from config import Config
from output_validator import OutputValidator


def _make_config():
    c = Config()
    # Minimal mock — just need the lookup sets
    c.ALLOWED_OBJECT_PARTS = {"car": {"hood", "door", "unknown"}}
    c.ALLOWED_ISSUE_TYPES = {"dent", "scratch", "crack", "none", "unknown"}
    c.ALLOWED_CLAIM_STATUS = {"supported", "contradicted", "not_enough_information"}
    c.ALLOWED_SEVERITY = {"none", "low", "medium", "high", "unknown"}
    c.ALLOWED_RISK_FLAGS = {"blurry_image", "manual_review_required", "claim_mismatch",
                            "possible_manipulation", "user_history_risk", "none"}
    return c


def _row(**overrides):
    base = {
        "user_id": "test", "image_paths": "img.jpg", "user_claim": "dent on door",
        "claim_object": "car", "evidence_standard_met": "true",
        "evidence_standard_met_reason": "ok", "risk_flags": "none", "issue_type": "dent",
        "object_part": "door", "claim_status": "supported",
        "claim_status_justification": "good match", "supporting_image_ids": "none",
        "valid_image": "true", "severity": "low",
    }
    base.update(overrides)
    return base


class TestConsistencyChecks:
    def setup_method(self):
        self.validator = OutputValidator(_make_config())

    def test_supported_with_none_damage_becomes_contradicted(self):
        row = _row(claim_status="supported", issue_type="none")
        result = self.validator.validate(row)
        assert result["claim_status"] == "contradicted"

    def test_supported_with_unknown_damage_becomes_not_enough(self):
        row = _row(claim_status="supported", issue_type="unknown")
        result = self.validator.validate(row)
        assert result["claim_status"] == "not_enough_information"

    def test_supported_with_valid_damage_stays_supported(self):
        row = _row(claim_status="supported", issue_type="dent")
        result = self.validator.validate(row)
        assert result["claim_status"] == "supported"

    def test_contradicted_without_evidence_becomes_not_enough(self):
        row = _row(claim_status="contradicted", issue_type="crack", evidence_standard_met="false")
        result = self.validator.validate(row)
        assert result["claim_status"] == "not_enough_information"

    def test_contradicted_with_evidence_stays_contradicted(self):
        row = _row(claim_status="contradicted", issue_type="none", evidence_standard_met="true")
        result = self.validator.validate(row)
        assert result["claim_status"] == "contradicted"

    def test_critical_flag_adds_manual_review(self):
        row = _row(claim_status="supported", issue_type="dent",
                   risk_flags="possible_manipulation")
        result = self.validator.validate(row)
        assert "manual_review_required" in result["risk_flags"]

    def test_bool_fields_normalized(self):
        row = _row(evidence_standard_met="False", valid_image="yes")
        result = self.validator.validate(row)
        assert result["evidence_standard_met"] == "false"
        assert result["valid_image"] == "true"

    def test_invalid_flags_removed(self):
        row = _row(risk_flags="blurry_image;invalid_flag;none")
        result = self.validator.validate(row)
        assert "invalid_flag" not in result["risk_flags"]
        assert "blurry_image" in result["risk_flags"]
