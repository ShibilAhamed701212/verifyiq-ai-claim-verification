# Make code/ a proper package so the stdlib code.py doesn't shadow it.
# Ensure code/ is on sys.path so V1 submodules can use bare imports (from utils import ...).

import sys
from pathlib import Path

_code_dir = str(Path(__file__).parent)
if _code_dir not in sys.path:
    sys.path.insert(0, _code_dir)
