"""VerifyIQ — Multi-Modal Claim Verification Platform.

VerifyIQ processes images and claim text to determine whether damage claims
are supported, contradicted, or need more evidence. It combines deterministic
rule engines with multi-modal VLM analysis for accurate, explainable decisions.
"""

import sys as _sys
from pathlib import Path as _Path
from importlib.metadata import PackageNotFoundError, version as _version

# V1 code is frozen at code/ — keep it importable for V2 adapters.
# The directory name collides with the standard-library ``code`` module, which
# is found first on sys.path (and is often already imported, e.g. by pdb or
# pytest). Put the project root ahead of it and drop a cached stdlib ``code``
# so ``import code.<module>`` resolves to this project's package.
_ROOT_DIR = str(_Path(__file__).resolve().parent.parent)
_CODE_DIR = str(_Path(_ROOT_DIR) / "code")
for _p in (_CODE_DIR, _ROOT_DIR):
    if _p in _sys.path:
        _sys.path.remove(_p)
    _sys.path.insert(0, _p)
_cached_code = _sys.modules.get("code")
if _cached_code is not None and not hasattr(_cached_code, "__path__"):
    del _sys.modules["code"]
del _cached_code

try:
    __version__ = _version("verifyiq")
except PackageNotFoundError:
    __version__ = "0.1.0-dev"
