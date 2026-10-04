"""Tests for image_validator."""

from pathlib import Path

from image_validator import all_images_valid, any_valid_images, validate_images


class TestImageValidator:
    def test_nonexistent_path_is_invalid(self):
        results = validate_images([Path("nonexistent.jpg")])
        assert len(results) == 1
        assert not results[0]["valid"]
        assert any("not found" in e for e in results[0]["errors"])

    def test_empty_list_returns_empty(self):
        results = validate_images([])
        assert results == []

    def test_any_valid_with_all_invalid(self):
        results = [{"valid": False}, {"valid": False}]
        assert not any_valid_images(results)

    def test_all_valid_with_empty(self):
        assert not all_images_valid([])
