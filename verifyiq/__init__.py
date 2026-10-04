"""VerifyIQ — Multi-Modal Claim Verification Platform.

VerifyIQ processes images and claim text to determine whether damage claims
are supported, contradicted, or need more evidence. It combines deterministic
rule engines with multi-modal VLM analysis for accurate, explainable decisions.
"""

import sys as _sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version
from pathlib import Path as _Path

# V1 code is frozen at code/ and uses bare imports (``from config import
# Config``). Put code/ on sys.path and import V1 modules by their bare names.
# The ``code`` package name itself is never imported from here: it collides
# with the standard-library ``code`` module (used by pdb), which must keep
# resolving to the stdlib.
_CODE_DIR = str(_Path(__file__).resolve().parent.parent / "code")
if _CODE_DIR not in _sys.path:
    _sys.path.insert(0, _CODE_DIR)

try:
    __version__ = _version("verifyiq")
except PackageNotFoundError:
    __version__ = "0.1.0-dev"
