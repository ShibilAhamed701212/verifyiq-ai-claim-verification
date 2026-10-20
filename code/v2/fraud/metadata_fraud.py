from code.v2.models.fraud import MetadataFraudResult
from datetime import datetime, timedelta

# Phones and cameras write their firmware version into the EXIF Software tag,
# so only names of actual image editors count as evidence of editing.
EDITING_SOFTWARE = (
    "photoshop", "lightroom", "gimp", "snapseed", "picsart", "pixelmator",
    "affinity photo", "paint.net", "canva", "facetune", "fotor", "luminar",
    "photoscape", "photodirector", "polarr",
)

# Photos of one incident are taken minutes apart; only a wide spread between
# capture times suggests images from different events.
TIMESTAMP_MISMATCH_THRESHOLD = timedelta(hours=24)


def _is_editing_software(value: str) -> bool:
    lowered = value.lower()
    return any(name in lowered for name in EDITING_SOFTWARE)


def _parse_exif_datetime(value: str) -> datetime | None:
    try:
        return datetime.strptime(value.strip().rstrip("\x00"), "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None


class MetadataFraudDetector:
    """Detects EXIF anomalies, editing software, timestamp mismatches."""

    def check(self, image_paths: list[str]) -> MetadataFraudResult:
        result = MetadataFraudResult()
        if not image_paths:
            return result

        editing_software_found = set()
        cameras = set()
        timestamps = []

        for p in image_paths:
            try:
                from PIL import Image
                from PIL.ExifTags import TAGS
                with Image.open(p) as img:
                    exif = img._getexif()
                if exif:
                    result.has_exif = True
                    for tag_id, value in exif.items():
                        tag_name = TAGS.get(tag_id, tag_id)
                        if tag_name == "Software" and _is_editing_software(str(value)):
                            editing_software_found.add(str(value))
                            result.has_editing = True
                        elif tag_name == "Model":
                            cameras.add(str(value))
                        elif tag_name == "DateTimeOriginal":
                            parsed = _parse_exif_datetime(str(value))
                            if parsed is not None:
                                timestamps.append(parsed)
                else:
                    result.flags.append("no_exif")
            except Exception:
                result.flags.append("exif_read_error")

        if editing_software_found:
            result.editing_software = "; ".join(editing_software_found)
        if len(cameras) > 1:
            result.camera_mismatch = list(cameras)
        if len(timestamps) > 1 and max(timestamps) - min(timestamps) > TIMESTAMP_MISMATCH_THRESHOLD:
            result.timestamp_mismatch = True

        score = 0.0
        if result.has_editing:
            score += 0.3
            result.flags.append("edited_image")
        if result.timestamp_mismatch:
            score += 0.3
            result.flags.append("timestamp_mismatch")
        if result.camera_mismatch:
            score += 0.2
            result.flags.append("camera_mismatch")
        if "no_exif" in result.flags:
            score += 0.1

        result.fraud_score = min(1.0, score)
        return result
