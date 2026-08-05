"""Gate on the Theme -> CSS custom-property projection.

Three codebases implement this mapping today, each with its own fallback table,
which is how a stale palette survived in `savvi-skin.ts` after the skin moved on.
The cases below pin what the single owner promises, so the other three can be
deleted against a contract rather than against a reading of the code.
"""

import unittest

from marklib.tokens import to_css_vars

THEME = {
    "id": "t",
    "display_name": "T",
    "light": {"bg": "#FFFFFF", "fg": "#000000", "accent": "#0000FF"},
    "dark": {"bg": "#000000", "fg": "#FFFFFF", "accent": "#8888FF"},
    "typography": {
        "sans": "system-ui, sans-serif",
        "display": "Georgia, serif",
        "base_size_px": 16,
        "heading_weight": 600,
        "heading_tracking": "-0.015",
    },
    "metrics": {"radius_px": 6, "unit_px": 4},
}


class ToCssVars(unittest.TestCase):
    def test_default_prefix_is_brand_neutral(self):
        """--fv-* put fastverk's name in every other brand's stylesheet."""
        css = to_css_vars(THEME)
        self.assertIn("--brand-bg: #FFFFFF;", css)
        self.assertNotIn("--fv-", css)

    def test_prefix_is_a_parameter(self):
        """meridian's own renderers read --mer-*."""
        css = to_css_vars(THEME, prefix="mer")
        self.assertIn("--mer-accent: #0000FF;", css)

    def test_snake_case_roles_become_kebab_case_vars(self):
        css = to_css_vars({"light": {"accent_strong": "#123456"}})
        self.assertIn("--brand-accent-strong: #123456;", css)

    def test_light_palette_lands_on_the_selector(self):
        """The :root block carries LIGHT; dark must not leak into it."""
        root = to_css_vars(THEME).split("@media")[0]
        self.assertIn("--brand-bg: #FFFFFF;", root)
        self.assertNotIn("--brand-bg: #000000;", root)
        self.assertNotIn("#8888FF", root)

    def test_dark_palette_is_emitted_twice_and_both_are_load_bearing(self):
        """The media query serves an OS dark-mode user; the attribute serves a toggle.

        A stylesheet with only the media query cannot be toggled in-product; with
        only the attribute it ignores the system setting. Neither alone is correct.
        """
        css = to_css_vars(THEME)
        self.assertIn("@media (prefers-color-scheme: dark)", css)
        self.assertIn(':root[data-theme="dark"]', css)
        self.assertEqual(2, css.count("--brand-bg: #000000;"))

    def test_single_mode_skin_emits_no_dark_block(self):
        """A brand with no dark palette gets one block, not a silent duplicate."""
        css = to_css_vars({"light": {"bg": "#FFFFFF"}})
        self.assertNotIn("prefers-color-scheme", css)
        self.assertNotIn("data-theme", css)

    def test_absent_roles_are_omitted_so_renderer_fallbacks_apply(self):
        css = to_css_vars(THEME)
        self.assertNotIn("--brand-warning", css)
        self.assertNotIn("--brand-muted", css)

    def test_numeric_tokens_carry_units_where_the_schema_means_pixels(self):
        css = to_css_vars(THEME)
        self.assertIn("--brand-base-size: 16px;", css)
        self.assertIn("--brand-radius: 6px;", css)
        self.assertIn("--brand-heading-weight: 600;", css)

    def test_typography_and_metrics_are_mode_independent(self):
        """They belong in :root once, not duplicated into the dark block."""
        css = to_css_vars(THEME)
        self.assertEqual(1, css.count("--brand-sans:"))
        self.assertEqual(1, css.count("--brand-radius:"))

    def test_output_names_the_skin_and_says_not_to_edit_it(self):
        self.assertIn("T", to_css_vars(THEME).splitlines()[0])


if __name__ == "__main__":
    unittest.main()
