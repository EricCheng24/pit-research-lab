"""Make the preserved, input-only WU-01B seam available to standalone tests."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "cap_f2_wu01"))
