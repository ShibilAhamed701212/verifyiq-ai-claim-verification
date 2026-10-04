"""
Wrong object detection using deterministic heuristics.
Compares image properties against expected claim object type.
"""

from pathlib import Path

import cv2


class ObjectValidator:
    """Validates that the image object matches the claimed object type."""

    # Color profiles for common objects (BGR ranges)
    OBJECT_PROFILES = {
        "car": {
            "min_dim": 100,
            "aspect_min": 0.5,
            "aspect_max": 4.0,
        },
        "laptop": {
            "min_dim": 100,
            "aspect_min": 0.5,
            "aspect_max": 3.0,
        },
        "package": {
            "min_dim": 100,
            "aspect_min": 0.3,
            "aspect_max": 4.0,
        },
    }

    def __init__(self):
        pass

    def validate(self, image_path: Path, claim_object: str) -> dict:
        if not image_path.exists():
            return {"object_match": True, "confidence": 0.0, "reason": "Image not found"}

        profile = self.OBJECT_PROFILES.get(claim_object)
        if profile is None:
            return {"object_match": True, "confidence": 1.0, "reason": f"Unknown object type: {claim_object}"}

        img = cv2.imread(str(image_path))
        if img is None or img.size == 0:
            return {"object_match": True, "confidence": 0.0, "reason": "Could not read image"}

        h, w = img.shape[:2]
        aspect = max(w, h) / min(w, h) if min(w, h) > 0 else 99
        min_dim = min(h, w)

        reasons = []

        if min_dim < profile["min_dim"]:
            reasons.append(f"Image too small ({min_dim}px) for {claim_object}")
        if aspect < profile["aspect_min"] or aspect > profile["aspect_max"]:
            reasons.append(f"Aspect ratio {aspect:.1f} atypical for {claim_object}")

        is_mismatch = bool(reasons)
        return {
            "object_match": not is_mismatch,
            "confidence": 0.0 if is_mismatch else 1.0,
            "reason": "; ".join(reasons) if reasons else f"Dimensions consistent with {claim_object}",
        }

    def find_wrong_objects(self, image_paths: list, claim_object: str) -> list:
        results = []
        for p in image_paths:
            result = self.validate(p, claim_object)
            results.append({
                "image_id": p.stem,
                "wrong_object": not result["object_match"],
                "reason": result["reason"],
            })
        return results
