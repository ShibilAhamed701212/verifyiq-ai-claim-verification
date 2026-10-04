"""
Crop and obstruction detector using edge analysis and aspect ratio.
"""

from pathlib import Path

import cv2
import numpy as np


class CropDetector:
    """Detects excessively cropped or obstructed images."""

    def __init__(self, min_visible_ratio: float = 0.3, max_aspect_ratio: float = 3.0):
        self.min_visible_ratio = min_visible_ratio
        self.max_aspect_ratio = max_aspect_ratio

    def is_cropped(self, image_path: Path) -> bool:
        if not image_path.exists():
            return False
        img = cv2.imread(str(image_path))
        if img is None or img.size == 0:
            return False
        h, w = img.shape[:2]
        if h == 0 or w == 0:
            return False

        aspect = max(w, h) / min(w, h) if min(w, h) > 0 else 99
        if aspect > self.max_aspect_ratio:
            return True

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)

        border_thickness = max(1, min(h, w) // 20)
        offset = border_thickness * 2
        if offset >= h or offset >= w:
            return False

        # Check edge density in a band just inside the border (avoids false edge from Sobel boundary)
        top_edge = np.mean(edges[border_thickness:offset, :] > 0)
        bottom_edge = np.mean(edges[-offset:-border_thickness, :] > 0)
        left_edge = np.mean(edges[:, border_thickness:offset] > 0)
        right_edge = np.mean(edges[:, -offset:-border_thickness] > 0)
        edge_density = (top_edge + bottom_edge + left_edge + right_edge) / 4

        if edge_density > 0.5:
            return True

        return False

    def has_cropped_images(self, image_paths: list) -> list:
        results = []
        for p in image_paths:
            results.append({
                "image_id": p.stem,
                "is_cropped": self.is_cropped(p),
            })
        return results
