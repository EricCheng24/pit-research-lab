"""Expose preserved input-only helpers without mutating their test packages."""

import sys
from pathlib import Path

for folder in ("cap_f2_wu01", "cap_f2_v1_a03", "cap_f2_v1_a04"):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / folder))
