"""Gate on the Catalog gate.

The property under test is asymmetric and easy to get backwards: declaring a kind
you do not ship is an ERROR, shipping a kind you did not declare is FINE.
`Catalog` states the floor a complete brand meets, not the ceiling — a brand that
adds a terminal theme before updating its spec should not fail the build for it.

Reverse the comparison and nothing looks wrong: the gate still passes for a
conformant package and still fails for some non-conformant ones, just not the
ones that matter.
"""

import os
import tempfile
import unittest

from tools.catalog_check import check, main


def _manifest(declared, present):
    return {
        "spec": {"id": "t", "catalog": {"kinds": list(declared)}},
        "assets": [{"name": "a%d" % i, "kind": k} for i, k in enumerate(present)],
    }


class Check(unittest.TestCase):
    def test_conformant_when_every_declared_kind_is_present(self):
        missing, present = check(_manifest(["A", "B"], ["A", "B"]))
        self.assertEqual([], missing)
        self.assertEqual(["A", "B"], present)

    def test_a_declared_kind_with_no_asset_is_the_failure(self):
        """citizen-sh's real bug: it declared MDBOOK_THEME and shipped none.
        Nothing errored -- rules_brand generated an empty filegroup and the docs
        would have built unstyled."""
        missing, _ = check(_manifest(["A", "MDBOOK"], ["A"]))
        self.assertEqual(["MDBOOK"], missing)

    def test_shipping_MORE_than_declared_is_fine(self):
        """The floor, not the ceiling. A brand that adds an artifact before
        updating its spec should not fail the build for being generous."""
        missing, present = check(_manifest(["A"], ["A", "B", "C"]))
        self.assertEqual([], missing)
        self.assertEqual(["A", "B", "C"], present)

    def test_no_catalog_declares_nothing_and_passes(self):
        """A spec need not have a Catalog; absence is not a claim."""
        missing, _ = check({"spec": {"id": "t"}, "assets": [{"name": "a", "kind": "A"}]})
        self.assertEqual([], missing)

    def test_an_asset_with_no_kind_cannot_satisfy_a_declaration(self):
        """`kind` is optional on an Asset, and an unkinded asset is exactly the
        thing that must NOT be counted as satisfying a declared kind."""
        manifest = {
            "spec": {"id": "t", "catalog": {"kinds": ["A"]}},
            "assets": [{"name": "a"}],
        }
        missing, _ = check(manifest)
        self.assertEqual(["A"], missing)


class Cli(unittest.TestCase):
    def _run(self, manifest):
        import json
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "brand.json")
            with open(src, "w", encoding="utf-8") as fh:
                json.dump(manifest, fh)
            out = os.path.join(d, "report.txt")
            rc = main(["--manifest", src, "--out", out])
            text = open(out, encoding="utf-8").read() if os.path.exists(out) else ""
        return rc, text

    def test_exits_nonzero_and_writes_nothing_when_short(self):
        """The report must not exist on failure: a genrule whose output appeared
        anyway would let the archive build on a stale report."""
        rc, text = self._run(_manifest(["A", "B"], ["A"]))
        self.assertEqual(1, rc)
        self.assertEqual("", text)

    def test_exits_zero_and_reports_when_conformant(self):
        rc, text = self._run(_manifest(["A"], ["A"]))
        self.assertEqual(0, rc)
        self.assertIn("conformant", text)
        self.assertIn("A", text)


if __name__ == "__main__":
    unittest.main()
