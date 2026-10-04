"""
Blur detector using Laplacian variance.
"""

from pathlib import Path

import cv2


class BlurDetector:
    """Deterministic blur detection using Laplacian variance."""

    def __init__(self, threshold: float = 15.0):
        self.threshold = threshold

    def is_blurry(self, image_path: Path) -> bool:
        if not image_path.exists():
            return False
        img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        if img is None or img.size == 0:
            return False
        laplacian_var = cv2.Laplacian(img, cv2.CV_64F).var()
        return laplacian_var < self.threshold

    def has_blurry_images(self, image_paths: list) -> list:
        results = []
        for p in image_paths:
            results.append({
                "image_id": p.stem,
                "is_blurry": self.is_blurry(p),
            })
        return results
