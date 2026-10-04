"""
Deterministic claim parser.

Extracts the claimed damage type and object part from the user conversation
using normalization, keyword matching, and simple regex-friendly phrase checks.
"""

import re

from config import Config
from utils import normalize_text


class ClaimParser:
    """Parses user claim text into normalized challenge enum values."""

    def __init__(self, config: Config):
        self.config = config

    def parse(self, user_claim: str, claim_object: str) -> dict[str, str]:
        claim_text = user_claim or ""
        customer_text = self._filter_customer_text(claim_text)
        text = normalize_text(customer_text)
        claim_object = (claim_object or "").lower()

        return {
            "claimed_damage_type": self._damage_type(text),
            "claimed_object_part": self._object_part(text, claim_object),
            "claim_text": claim_text,
        }

    @staticmethod
    def _filter_customer_text(text: str) -> str:
        """Keep only Customer: messages, filtering out Support/Agent lines."""
        if " | " in text:
            parts = text.split(" | ")
            customer_parts = [
                p.split(":", 1)[1].strip()
                for p in parts
                if p.strip().lower().startswith("customer:")
            ]
            return " | ".join(customer_parts) if customer_parts else text
        lines = text.split("\n")
        customer_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.lower().startswith("customer:"):
                customer_lines.append(stripped.split(":", 1)[1].strip())
            elif not any(stripped.lower().startswith(p) for p in ("support:", "agent:", "user:")):
                customer_lines.append(stripped)
        return " | ".join(customer_lines) if customer_lines else text

    def _damage_type(self, text: str) -> str:
        patterns = [
            ("glass_shatter", ["shatter", "shattered", "smashed glass", "broken glass"]),
            ("water_damage", ["water damage", "water", "wet", "moisture", "liquid", "spill"]),
            ("torn_packaging", ["torn", "ripped", "tear"]),
            ("crushed_packaging", ["crushed", "crush", "dented box"]),
            ("broken_part", ["broken", "broke", "snapped", "not working", "not sitting"]),
            ("missing_part", ["missing", "lost", "gone"]),
            ("scratch", ["scratch", "scrape", "scraped", "scuff", "mark"]),
            ("crack", ["crack", "cracked", "fracture"]),
            ("dent", ["dent", "dented", "deformation"]),
            ("stain", ["stain", "stained", "discoloration"]),
        ]
        for damage_type, keywords in patterns:
            if any(keyword in text for keyword in keywords):
                return damage_type
        return "unknown"

    @staticmethod
    def _is_negated(text: str, keyword: str, window: int = 25) -> bool:
        """Check if keyword is negated by 'not' or 'no' within `window` chars before it."""
        idx = text.find(keyword)
        if idx == -1:
            return False
        start = max(0, idx - window)
        before = text[start:idx]
        return bool(re.search(r'\b(no|not)\b', before))

    def _object_part(self, text: str, claim_object: str) -> str:
        part_keywords = {
            "car": [
                ("front_bumper", ["front bumper", "bumper front", "front side"]),
                ("rear_bumper", ["rear bumper", "back bumper", "rear side", "back of the car"]),
                ("side_mirror", ["side mirror", "mirror"]),
                ("windshield", ["windshield", "windscreen", "front glass"]),
                ("headlight", ["headlight", "head light"]),
                ("taillight", ["taillight", "tail light"]),
                ("quarter_panel", ["quarter panel"]),
                ("fender", ["fender"]),
                ("door", ["door", "door panel"]),
                ("hood", ["hood", "bonnet"]),
                ("body", ["body", "panel"]),
            ],
            "laptop": [
                ("hinge", ["hinge"]),
                ("screen", ["screen", "display"]),
                ("keyboard", ["keyboard", "keycap", "keys"]),
                ("trackpad", ["trackpad", "touchpad"]),
                ("lid", ["lid", "top cover"]),
                ("corner", ["corner", "edge"]),
                ("port", ["port", "charging slot", "usb"]),
                ("base", ["base", "bottom"]),
                ("body", ["body", "casing", "chassis"]),
            ],
            "package": [
                ("seal", ["seal", "tape", "flap"]),
                ("package_corner", ["corner"]),
                ("package_side", ["side"]),
                ("label", ["label", "sticker", "barcode"]),
                ("contents", ["contents", "inside", "interior"]),
                ("item", ["item", "product"]),
                ("box", ["box", "package", "carton"]),
            ],
        }

        for part, keywords in part_keywords.get(claim_object, []):
            for keyword in keywords:
                if keyword in text and not self._is_negated(text, keyword):
                    return part
        return "unknown"
