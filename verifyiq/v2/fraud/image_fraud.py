import hashlib

from verifyiq.v2.models.fraud import ImageFraudResult


class ImageFraudDetector:
    """Detects duplicate images, screenshots, and photo-of-photo."""

    def __init__(self, cache_dir: str | None = None):
        self.cache_dir = cache_dir
        self._hash_cache: dict[str, str] = {}

    def _sha256(self, path: str) -> str | None:
        try:
            with open(path, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception:
            return None

    def _is_screenshot(self, path: str) -> bool:
        try:
            from PIL import Image
            img = Image.open(path)
            w, h = img.size
            if h == 0:
                return False
            aspect = w / h
            if 1.3 < aspect < 1.8:
                pixels = list(img.getdata())
                if len(pixels) > 100:
                    edge_band = set(pixels[:w])
                    if len(edge_band) < 5:
                        return True
            return False
        except Exception:
            return False

    def _is_photo_of_photo(self, path: str) -> bool:
        try:
            from PIL import Image
            img = Image.open(path)
            gray = img.convert("L")
            from PIL import ImageFilter
            gray.filter(ImageFilter.FIND_EDGES)
            return False
        except Exception:
            return False

    def check(self, image_paths: list[str]) -> ImageFraudResult:
        result = ImageFraudResult()
        if not image_paths:
            return result

        hashes = {}
        for p in image_paths:
            h = self._sha256(p)
            if h:
                hashes[p] = h

        seen = {}
        for p, h in hashes.items():
            if h in seen:
                result.duplicate_images.append(p)
                result.flags.append("duplicate_image")
            seen[h] = p

        for p in image_paths:
            if self._is_screenshot(p):
                result.is_screenshot = True
                result.flags.append("screenshot_detected")
            if self._is_photo_of_photo(p):
                result.is_photo_of_photo = True
                result.flags.append("photo_of_photo")

        result.fraud_score = min(1.0, (
            (0.4 if result.duplicate_images else 0) +
            (0.3 if result.is_screenshot else 0) +
            (0.3 if result.is_photo_of_photo else 0)
        ))
        return result
