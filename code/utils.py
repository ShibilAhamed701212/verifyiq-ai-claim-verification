"""
Utility functions for file I/O, logging, and general helpers.
"""

import csv
import logging
import re
import sys
from pathlib import Path


def setup_logging(level=logging.INFO) -> logging.Logger:
    logger = logging.getLogger("evidence_review")
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


def ensure_output_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def parse_image_paths(image_paths_str: str, base_dir: Path) -> list[Path]:
    if not image_paths_str or image_paths_str.strip() == "":
        return []

    paths = []
    for part in image_paths_str.split(";"):
        part = part.strip()
        if not part:
            continue
        p = Path(part)
        if not p.is_absolute():
            p = base_dir / p
        paths.append(p)
    return paths


def get_image_id_from_path(path: Path) -> str:
    return path.stem


def safe_csv_read(csv_path: Path) -> list[dict]:
    rows = []
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if all(v == "" for v in row.values()):
                continue
            rows.append(row)
    return rows


def normalize_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.lower().strip())


def extract_claim_text(user_claim: str) -> str:
    if not user_claim:
        return ""

    # Handle pipe-separated "Customer: ... | Support: ... | Customer: ..." format
    if " | " in user_claim:
        parts = user_claim.split(" | ")
        customer_lines = []
        for part in parts:
            part = part.strip()
            if part.lower().startswith("customer:"):
                customer_lines.append(part[9:].strip())
        if customer_lines:
            return customer_lines[-1]
        return parts[-1].strip()

    # Handle multi-line "User: / Agent:" format
    lines = user_claim.split("\n")
    claim_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.lower().startswith("user:"):
            claim_lines.append(line[5:].strip())
        elif line.lower().startswith("agent:"):
            continue
        else:
            claim_lines.append(line)

    return " ".join(claim_lines)


def clamp(value, min_val, max_val):
    return max(min_val, min(max_val, value))
