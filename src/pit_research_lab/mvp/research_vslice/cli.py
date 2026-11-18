"""Offline CLI. Explicit new output directory outside checkout; no repository writes."""

import argparse
from pathlib import Path

from .contracts import ResearchError, require, research_bytes
from .replay import execute
from .sources import checkout_root


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--rule-threshold", type=int, default=105)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        out = args.output_dir
        require(
            out.is_absolute() and ".." not in out.parts and not out.is_relative_to(checkout_root()),
            "OUTPUT_MUST_BE_OUTSIDE_CHECKOUT",
        )
        for p in (*reversed(out.parents), out):
            require(not p.is_symlink(), "OUTPUT_SYMLINK_REFUSED")
        require(not out.exists(), "OUTPUT_ALREADY_EXISTS")
        trace, manifest = execute(args.seed, args.rule_threshold)
        out.mkdir(parents=True, exist_ok=False)
        (out / "trace.json").write_bytes(trace)
        (out / "manifest.json").write_bytes(research_bytes(manifest))
        print(manifest["trace_sha256"])
    except (ResearchError, OSError):
        parser.exit(2, "RESEARCH_RUN_REFUSED\n")


if __name__ == "__main__":
    main()
