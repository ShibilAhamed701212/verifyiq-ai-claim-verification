import re
from pathlib import Path


class InputSanitizer:
    """Sanitizes inputs against prompt injection, path traversal, CSV injection."""

    @staticmethod
    def sanitize_claim_text(text: str) -> str:
        """Wrap user claim text with instruction boundaries to prevent prompt injection."""
        if not text:
            return ""
        # Strip known prompt injection patterns
        injection_patterns = [
            r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|commands)",
            r"ignore\s+everything",
            r"forget\s+(all\s+)?(previous|prior|above)",
            r"you\s+are\s+(now|not\s+required\s+to)",
            r"system\s+prompt",
            r"new\s+instructions",
            r"override",
            r"disregard(\s+all\s+previous)?",
            r"you\s+must\s+now",
            r"your\s+new\s+task\s+is",
            r"from\s+now\s+on",
            r"redefine\s+your\s+purpose",
        ]
        sanitized = text[:1000]  # Hard length limit
        for pattern in injection_patterns:
            sanitized = re.sub(pattern, "[REDACTED]", sanitized, flags=re.IGNORECASE)
        return sanitized

    @staticmethod
    def sanitize_image_path(path: str, base_dir: str) -> str:
        """Prevent path traversal outside allowed directory."""
        try:
            # Null byte check
            if "\x00" in path or "\x00" in base_dir:
                return ""

            # Explicit path traversal pattern checks (cross-platform)
            if re.search(r"(?:^|[\\/])\.\.[\\/]|(?:^|[\\/])\.\.$", path):
                return ""

            base = Path(base_dir).resolve()
            target = (base / path).resolve()

            # Symlink-aware check: ensure normalized target is within base.
            # A plain string-prefix test would accept sibling directories
            # such as "<base>-other/...", so compare path components.
            if not target.is_relative_to(base):
                return ""  # Path traversal detected
            return str(target)
        except Exception:
            return ""

    @staticmethod
    def sanitize_csv_field(value: str) -> str:
        """Prevent CSV injection (formula execution in Excel/Calc)."""
        if not value:
            return ""
        # Detect leading dangerous characters and tab-based injection
        if value[0] in ("=", "+", "-", "@", "|", "\t", "\x09"):
            # Wrap in double-quotes for better Excel compatibility, prefix with ' for safety
            return "'" + '"' + value + '"'
        # Detect tab character anywhere in the field (tab-hijacking)
        if "\t" in value:
            return "'" + value
        return value

    @staticmethod
    def sanitize_filename(name: str) -> str:
        """Remove dangerous characters from filenames."""
        return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name)
