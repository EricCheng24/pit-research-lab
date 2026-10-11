"""Minimal command-line interface for the installed package."""

import argparse
from importlib.metadata import version


def main() -> None:
    """Display help or the installed distribution version."""
    parser = argparse.ArgumentParser(description="PIT Research Lab package information.")
    parser.add_argument("--version", action="version", version=version("pit-research-lab"))
    parser.parse_args()
