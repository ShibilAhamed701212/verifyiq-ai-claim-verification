"""Shared pytest setup.

The V1 sources live in a directory named ``code`` and use bare imports
(``from config import Config``). Importing ``verifyiq`` puts the project root
and ``code/`` on sys.path and evicts the stdlib ``code`` module that pytest
has already imported, so both test suites can import the project package.
"""

import verifyiq  # noqa: F401
