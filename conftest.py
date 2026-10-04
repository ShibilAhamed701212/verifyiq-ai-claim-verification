"""Shared pytest setup.

The V1 sources live in a directory named ``code``. The test suites under
``code/tests`` and ``code/v2/tests`` (and the ``code/v2`` modules they test)
import it as a package (``code.v2...``), but pytest has already imported the
standard-library ``code`` module by the time it collects them. For the test
process only, put the project root first on sys.path and drop the cached
stdlib module so ``code`` resolves to the project package.

The installable ``verifyiq`` package does not rely on this: it imports the V1
modules by their bare names and leaves the stdlib ``code`` module alone.
"""

import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parent)
if _ROOT in sys.path:
    sys.path.remove(_ROOT)
sys.path.insert(0, _ROOT)

_cached = sys.modules.get("code")
if _cached is not None and not hasattr(_cached, "__path__"):
    del sys.modules["code"]

import verifyiq  # noqa: E402,F401  (puts code/ on sys.path)
