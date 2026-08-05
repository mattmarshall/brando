"""Pin the marklib package surface.

Every brand's `gen_<mark>.py` imports these names from the package root, so the
re-export list in `__init__.py` is a published API for six repos. Two ways it
breaks, both quiet:

  * A name is dropped or renamed during a refactor. Nothing in brando fails,
    because brando's own selfbrand generators import a subset; six brand repos
    fail on their next build instead.
  * `__init__.py` is emptied. This happened twice while writing 0.2.0 — an empty
    file is valid Python and a valid package, so the only symptom was a confusing
    `cannot import name 'Canvas'` from one unrelated test.

A surface test turns both into an immediate, named failure.
"""

import unittest

import marklib

EXPECTED_SURFACE = {
    "Canvas",
    "Layer",
    "Transform",
    "fit",
    "geom_to_path",
    "linear_gradient",
    "rounded_square",
    "spec_at",
    "vertical_gradient",
}


class Surface(unittest.TestCase):
    def test_every_published_name_is_importable(self):
        missing = sorted(n for n in EXPECTED_SURFACE if not hasattr(marklib, n))
        self.assertEqual([], missing, f"marklib no longer exports: {missing}")

    def test_the_package_is_not_empty(self):
        """The specific failure that bit twice: a valid, empty __init__.py."""
        self.assertTrue(
            hasattr(marklib, "Canvas"),
            "marklib/__init__.py appears to be empty — the package re-exports nothing",
        )

    def test_all_matches_what_is_actually_exported(self):
        """__all__ drifting from the imports is how a name silently stops working."""
        self.assertEqual(EXPECTED_SURFACE, set(marklib.__all__))
        for name in marklib.__all__:
            self.assertTrue(hasattr(marklib, name), f"__all__ names missing {name}")

    def test_submodules_are_importable_without_the_geometry_stack(self):
        """tokens and palette are stdlib-only on purpose — keep them that way."""
        import marklib.palette  # noqa: F401
        import marklib.tokens  # noqa: F401


if __name__ == "__main__":
    unittest.main()
