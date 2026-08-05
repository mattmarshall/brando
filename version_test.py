"""Assert `version.bzl` matches `MODULE.bazel`.

MODULE.bazel cannot load(), so the version necessarily exists twice. This makes
the copy that is stamped into every .brando as provenance follow the copy that
Bazel resolves — the first release of `brand_package` shipped them disagreeing.
"""

import os
import re
import unittest


class Version(unittest.TestCase):
    def test_version_bzl_matches_module_bazel(self):
        with open(os.environ["MODULE_BAZEL"], encoding="utf-8") as fh:
            module = re.search(r'version\s*=\s*"([^"]+)"', fh.read())
        with open(os.environ["VERSION_BZL"], encoding="utf-8") as fh:
            declared = re.search(r'VERSION\s*=\s*"([^"]+)"', fh.read())
        self.assertIsNotNone(module, "no version in MODULE.bazel")
        self.assertIsNotNone(declared, "no VERSION in version.bzl")
        self.assertEqual(
            module.group(1),
            declared.group(1),
            "version.bzl is stamped into every .brando as provenance; it must "
            "track MODULE.bazel",
        )
