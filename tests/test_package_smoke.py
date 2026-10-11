"""Verify that the package imports and its installed metadata is available."""

import importlib
from importlib.metadata import distribution
import unittest


class PackageSmokeTest(unittest.TestCase):
    def test_installed_package(self):
        package = importlib.import_module("pit_research_lab")
        installed = distribution("pit-research-lab")

        self.assertEqual(package.__name__, "pit_research_lab")
        self.assertEqual(installed.metadata["Name"], "pit-research-lab")
        self.assertEqual(installed.version, "0.1.0")


if __name__ == "__main__":
    unittest.main()
