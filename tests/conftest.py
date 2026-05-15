"""Shared pytest setup. Adds the repo root to sys.path so ``locomotion`` and
``hermes_tools`` import cleanly without needing an editable install."""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
