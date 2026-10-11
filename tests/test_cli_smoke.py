"""Verify the installed console entry point without external services."""

import subprocess
import unittest
from importlib.metadata import version


class CliSmokeTest(unittest.TestCase):
    def test_help(self):
        result = subprocess.run(["pitlab", "--help"], capture_output=True, text=True, check=False)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("usage: pitlab", result.stdout)
        self.assertIn("--help", result.stdout)
        self.assertIn("--version", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_version(self):
        result = subprocess.run(
            ["pitlab", "--version"], capture_output=True, text=True, check=False
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), version("pit-research-lab"))
        self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
