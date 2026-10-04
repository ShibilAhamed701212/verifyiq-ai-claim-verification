"""Tests for deterministic CV modules."""
import sys, unittest, tempfile, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "code"))

import numpy as np
from PIL import Image
from cv.blur_detector import BlurDetector
from cv.crop_detector import CropDetector
from cv.text_detector import TextDetector
from cv.object_validator import ObjectValidator


def _make_test_image(size, color=(200, 200, 200), noise=0):
    """Create a test image with optional noise."""
    arr = np.full((size[1], size[0], 3), color, dtype=np.uint8)
    if noise > 0:
        noise_arr = np.random.randint(0, noise, (size[1], size[0], 3), dtype=np.uint8)
        arr = np.clip(arr.astype(np.int16) + noise_arr.astype(np.int16), 0, 255).astype(np.uint8)
    return arr


class TestBlurDetector(unittest.TestCase):

    def setUp(self):
        self.detector = BlurDetector(threshold=100.0)
        self.tmpdir = Path(tempfile.mkdtemp())

    def _save(self, name, arr):
        path = self.tmpdir / name
        Image.fromarray(arr).save(path)
        return path

    def test_sharp_image_not_blurry(self):
        arr = _make_test_image((400, 300), noise=30)
        path = self._save("sharp.jpg", arr)
        self.assertFalse(self.detector.is_blurry(path))

    def test_uniform_image_is_blurry(self):
        arr = _make_test_image((400, 300), noise=0)
        path = self._save("uniform.jpg", arr)
        self.assertTrue(self.detector.is_blurry(path))

    def test_nonexistent_path_returns_false(self):
        self.assertFalse(self.detector.is_blurry(self.tmpdir / "nonexistent.jpg"))


class TestCropDetector(unittest.TestCase):

    def setUp(self):
        self.detector = CropDetector()
        self.tmpdir = Path(tempfile.mkdtemp())

    def _save(self, name, arr):
        path = self.tmpdir / name
        Image.fromarray(arr).save(path)
        return path

    def test_normal_image_not_cropped(self):
        arr = _make_test_image((800, 600), noise=20)
        path = self._save("normal.jpg", arr)
        self.assertFalse(self.detector.is_cropped(path))

    def test_extreme_aspect_ratio_is_cropped(self):
        arr = _make_test_image((1200, 100), noise=20)
        path = self._save("wide.jpg", arr)
        self.assertTrue(self.detector.is_cropped(path))

    def test_nonexistent_path_returns_false(self):
        self.assertFalse(self.detector.is_cropped(self.tmpdir / "nonexistent.jpg"))


class TestObjectValidator(unittest.TestCase):

    def setUp(self):
        self.validator = ObjectValidator()
        self.tmpdir = Path(tempfile.mkdtemp())

    def _save(self, name, arr):
        path = self.tmpdir / name
        Image.fromarray(arr).save(path)
        return path

    def test_laptop_sized_image_matches_laptop(self):
        arr = _make_test_image((800, 500), noise=20)
        path = self._save("laptop.jpg", arr)
        result = self.validator.validate(path, "laptop")
        self.assertTrue(result["object_match"])

    def test_tiny_image_mismatches_car(self):
        arr = _make_test_image((50, 50), noise=10)
        path = self._save("tiny.jpg", arr)
        result = self.validator.validate(path, "car")
        self.assertFalse(result["object_match"])

    def test_unknown_object_defaults_to_match(self):
        arr = _make_test_image((400, 300), noise=20)
        path = self._save("unknown.jpg", arr)
        result = self.validator.validate(path, "unknown_object")
        self.assertTrue(result["object_match"])


if __name__ == "__main__":
    unittest.main()
