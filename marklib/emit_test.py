"""Gate on the generator side of the outs contract.

The backwards-compatible path is the one worth pinning. Six brand repos still
invoke their generators as `gen.py <out-dir>` with the lists as module constants,
and they must keep working while they migrate — if `parse_args` stopped honouring
its defaults, every one of them would emit nothing and the failure would look like
a Bazel problem rather than a brando one.
"""

import unittest

from marklib.emit import parse_args


class ParseArgs(unittest.TestCase):
    def test_legacy_positional_out_dir_still_works(self):
        """The pre-0.2.0 contract: `gen.py <out-dir>`, lists from the module."""
        e = parse_args(["/tmp/out"], prefix="brando", variants=["a", "b"], sizes=[512])
        self.assertEqual("/tmp/out", e.out_dir)
        self.assertEqual("brando", e.prefix)
        self.assertEqual(["a", "b"], e.variants)
        self.assertEqual([512], e.sizes)

    def test_out_dir_defaults_to_cwd(self):
        self.assertEqual(".", parse_args([]).out_dir)

    def test_flags_override_the_generators_own_defaults(self):
        """The migrated path: Starlark owns the list, the generator obeys it."""
        e = parse_args(
            ["/tmp/out", "--variant", "x", "--variant", "y", "--layer", "svg"],
            variants=["a", "b", "c"],
            layers=["svg", "bg.svg"],
        )
        self.assertEqual(["x", "y"], e.variants)
        self.assertEqual(["svg"], e.layers)

    def test_prefix_flag_overrides(self):
        e = parse_args(["/tmp/out", "--prefix", "leangres"], prefix="brando")
        self.assertEqual("leangres", e.prefix)

    def test_sizes_are_ints_not_strings(self):
        """A string here silently produces `foo_512.png` vs `foo_512.png` — but
        breaks any arithmetic the rasterizer does with the size."""
        e = parse_args(["/tmp/out", "--size", "512", "--size", "1024"])
        self.assertEqual([512, 1024], e.sizes)
        self.assertIsInstance(e.sizes[0], int)

    def test_partial_override_leaves_other_lists_alone(self):
        """Passing only --variant must not blank out the generator's sizes."""
        e = parse_args(["/tmp/out", "--variant", "x"], variants=["a"], sizes=[512, 1024])
        self.assertEqual(["x"], e.variants)
        self.assertEqual([512, 1024], e.sizes)

    def test_no_defaults_and_no_flags_yields_empty_lists(self):
        """A migrated generator emits nothing if the rule stops sending its list.

        Emitting nothing fails the build (Bazel declared outputs that never
        appeared), which is the loud failure we want — a stale fallback list would
        instead quietly emit the wrong set.
        """
        e = parse_args(["/tmp/out"])
        self.assertEqual([], e.variants)
        self.assertEqual([], e.layers)
        self.assertEqual([], e.sizes)


if __name__ == "__main__":
    unittest.main()
