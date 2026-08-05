"""Gate on the contrast arithmetic and the rule table.

The arithmetic is checked against values from the WCAG 2.1 definition rather than
against itself, because a contrast gate that is quietly wrong is worse than none:
it converts "nobody checked" into "something checked and said it was fine".
"""

import unittest

from marklib.palette import (
    CONTRAST_RULES,
    check_palette,
    check_theme,
    contrast_ratio,
    relative_luminance,
    rgb,
)


class Arithmetic(unittest.TestCase):
    def test_black_on_white_is_the_maximum_21_to_1(self):
        self.assertAlmostEqual(21.0, contrast_ratio("#000000", "#FFFFFF"), places=2)

    def test_identical_colours_are_1_to_1(self):
        self.assertAlmostEqual(1.0, contrast_ratio("#3B6FF0", "#3B6FF0"), places=6)

    def test_ratio_is_symmetric(self):
        self.assertAlmostEqual(
            contrast_ratio("#123456", "#FEDCBA"), contrast_ratio("#FEDCBA", "#123456")
        )

    def test_luminance_endpoints(self):
        self.assertAlmostEqual(0.0, relative_luminance("#000000"), places=6)
        self.assertAlmostEqual(1.0, relative_luminance("#FFFFFF"), places=6)

    def test_luminance_is_not_a_plain_average(self):
        """Green carries far more luminance than blue; a naive mean gets this wrong."""
        self.assertGreater(relative_luminance("#00FF00"), relative_luminance("#0000FF"))

    def test_shorthand_and_alpha_hex_parse(self):
        self.assertEqual((255, 255, 255), rgb("#fff"))
        self.assertEqual((17, 34, 51), rgb("#112233ff"))

    def test_bad_hex_fails_loudly(self):
        with self.assertRaises(ValueError):
            rgb("nope")


class Rules(unittest.TestCase):
    def test_a_failing_pair_is_reported_with_its_numbers(self):
        # #777777 on #FFFFFF is ~4.48:1 — just under AA, the realistic failure.
        failures = check_palette({"fg": "#777777", "bg": "#FFFFFF"}, "light")
        self.assertEqual(1, len(failures))
        self.assertEqual(("fg", "bg"), (failures[0].fg_role, failures[0].bg_role))
        self.assertLess(failures[0].ratio, 4.5)
        self.assertIn("body text", str(failures[0]))

    def test_a_passing_pair_is_silent(self):
        self.assertEqual([], check_palette({"fg": "#000000", "bg": "#FFFFFF"}, "light"))

    def test_absent_roles_are_skipped_not_failed(self):
        """A skin that does not express `warning` is not failing contrast."""
        failures = check_palette({"fg": "#000000", "bg": "#FFFFFF"}, "light")
        self.assertEqual([], failures)

    def test_border_is_held_to_the_non_text_threshold(self):
        """WCAG 1.4.11: hairlines need 3:1, not 4.5:1 — holding them to 4.5 would
        force every brand to darken its borders past what the design intends."""
        rule = next(r for r in CONTRAST_RULES if r[0] == "border")
        self.assertEqual(3.0, rule[2])
        # ~3.5:1 — passes as a border, would fail as text.
        self.assertEqual([], check_palette({"border": "#949494", "bg": "#FFFFFF"}, "light"))

    def test_text_only_roles_are_errors_and_ambiguous_roles_are_warnings(self):
        """The severity split, pinned.

        Running the flat table against the fleet flagged all six skins on
        `border`, which is a bad rule rather than six bad palettes. Only pairs
        whose usage is unambiguous may fail a build.
        """
        by_role = {(f, b): sev for f, b, _, sev, _ in CONTRAST_RULES}
        for pair in (("fg", "bg"), ("muted", "surface"), ("code_fg", "code_bg"),
                     ("on_accent", "accent")):
            self.assertEqual("error", by_role[pair], pair)
        for pair in (("accent", "bg"), ("success", "bg"), ("border", "bg")):
            self.assertEqual("warn", by_role[pair], pair)

    def test_failure_key_is_the_waiver_id(self):
        f = check_palette({"fg": "#777777", "bg": "#FFFFFF"}, "dark")[0]
        self.assertEqual("dark:fg/bg", f.key)

    def test_both_modes_are_checked_and_labelled(self):
        theme = {
            "light": {"fg": "#777777", "bg": "#FFFFFF"},
            "dark": {"fg": "#555555", "bg": "#000000"},
        }
        modes = {f.mode for f in check_theme(theme)}
        self.assertEqual({"light", "dark"}, modes)

    def test_on_accent_is_checked_against_accent_not_bg(self):
        """The pair that a canvas-only check misses entirely."""
        theme = {"light": {"accent": "#FFD400", "on_accent": "#FFFFFF", "bg": "#FFFFFF"}}
        pairs = {(f.fg_role, f.bg_role) for f in check_theme(theme)}
        self.assertIn(("on_accent", "accent"), pairs)


if __name__ == "__main__":
    unittest.main()
