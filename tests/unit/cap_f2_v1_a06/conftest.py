"""Only explicit synthetic input seams from preserved owner tests."""

import sys
from pathlib import Path

for folder in ("cap_f2_wu01", "cap_f2_v1_a03", "cap_f2_v1_a04", "cap_f2_v1_a05"):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / folder))
