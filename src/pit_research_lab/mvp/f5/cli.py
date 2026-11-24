"""Headless F5 entry. A hash/directory alone cannot establish genuine producer origin."""

import argparse
from collections.abc import Sequence
from pathlib import Path

from .contracts import F5Error, safe_reason
from .inputs import OriginWitness
from .replay import run_to_directory


def main(argv: Sequence[str] | None = None, *, origin_witness: OriginWitness | None = None) -> None:
    """Embedding entry: main(argv, origin_witness=independent_execution_verifier).

    The verifier is trusted code provided by an authorized host in each fresh
    process, not a CLI option, serialized grant or verifier imported from a path.
    It must establish external origin independently before returning a record.
    The standalone module has no authority provider and fails closed.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--f3-dir", type=Path)
    parser.add_argument("--f3-evidence-sha256")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = run_to_directory(
            args.output_dir,
            args.f3_dir,
            args.f3_evidence_sha256,
            origin_witness=origin_witness,
        )
    except (F5Error, OSError) as error:
        parser.exit(2, safe_reason(error) + "\n")
    if result["first_failure"] is not None:
        parser.exit(2, result["first_failure"] + "\n")
    print(result["evidence_sha256"])


if __name__ == "__main__":
    main()
