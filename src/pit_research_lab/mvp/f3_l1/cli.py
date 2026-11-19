"""Run from a pinned checkout; write only to a new absolute external directory."""

import argparse
from pathlib import Path

from pit_research_lab.mvp.f2.research_panel import PanelError

from .replay import run_to_directory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        attempt = run_to_directory(args.output_dir)
    except (PanelError, OSError) as error:
        code = str(error) if isinstance(error, PanelError) else "OUTPUT_IO_FAILURE"
        parser.exit(2, code + "\n")
    print(attempt["evidence_ref"])


if __name__ == "__main__":
    main()
