"""Reuse only preserved synthetic input factories, never expected answers."""

import sys
from pathlib import Path

for folder in ("cap_f2_wu01", "cap_f2_v1_a03"):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / folder))
