"""Gate on the template renderer.

The two behaviours worth pinning are the ones `sed` got wrong: an unresolved token
must fail rather than ship as literal `@ACCENT@`, and the LaTeX hex notation must
be a rendering flag rather than a second set of authored values.
"""

import unittest

from tools.render_template import render, tokens_from_theme

THEME = {
    "id": "t",
    "display_name": "T",
    "light": {"bg": "#FFFFFF", "fg": "#111111", "accent": "#0000FF"},
    "dark": {"bg": "#000000", "fg": "#EEEEEE", "accent": "#8888FF"},
    "typography": {"sans": "system-ui", "base_size_px": 16},
    "metrics": {"radius_px": 6},
}


class Tokens(unittest.TestCase):
    def test_palette_roles_are_addressed_by_mode(self):
        t = tokens_from_theme(THEME)
        self.assertEqual("#FFFFFF", t["LIGHT_BG"])
        self.assertEqual("#000000", t["DARK_BG"])
        self.assertEqual("#8888FF", t["DARK_ACCENT"])

    def test_no_house_nicknames(self):
        """`INK` and `CREAM` are fastverk's words for its own colours."""
        t = tokens_from_theme(THEME)
        for leaked in ("INK", "CREAM", "TERTIARY"):
            self.assertNotIn(leaked, t)

    def test_strip_hash_is_a_rendering_flag_not_a_second_palette(self):
        """LaTeX xcolor wants bare 6-hex; that is notation, not new authoring."""
        self.assertEqual("#0000FF", tokens_from_theme(THEME)["LIGHT_ACCENT"])
        self.assertEqual("0000FF", tokens_from_theme(THEME, strip_hash=True)["LIGHT_ACCENT"])

    def test_typography_and_metrics_are_mode_independent(self):
        t = tokens_from_theme(THEME)
        self.assertEqual("system-ui", t["SANS"])
        self.assertEqual("16", t["BASE_SIZE_PX"])
        self.assertEqual("6", t["RADIUS_PX"])

    def test_absent_roles_produce_no_token(self):
        t = tokens_from_theme(THEME)
        self.assertNotIn("LIGHT_WARNING", t)

    def test_mode_exposes_that_modes_roles_unprefixed(self):
        """A single-mode artifact (a LaTeX class) reads better saying @BG@."""
        self.assertEqual("#FFFFFF", tokens_from_theme(THEME, mode="light")["BG"])
        self.assertEqual("#000000", tokens_from_theme(THEME, mode="dark")["BG"])

    def test_mode_light_does_not_silently_render_dark(self):
        """Regression: the mode parameter was shadowed by the light/dark loop
        variable, so every artifact resolved to dark no matter what was asked."""
        t = tokens_from_theme(THEME, mode="light")
        self.assertEqual("#111111", t["FG"])
        self.assertNotEqual(t["FG"], t["DARK_FG"])

    def test_no_mode_means_no_unprefixed_palette_tokens(self):
        """Both modes are still available by name; only the shorthand is gated."""
        t = tokens_from_theme(THEME)
        self.assertNotIn("BG", t)
        self.assertIn("DARK_BG", t)


class Render(unittest.TestCase):
    def test_substitutes_every_occurrence(self):
        self.assertEqual(
            "a #000000 b #000000",
            render("a @DARK_BG@ b @DARK_BG@", tokens_from_theme(THEME)),
        )

    def test_an_unresolved_token_fails_the_build(self):
        """sed substituted what it matched and said nothing about what it didn't,
        so a renamed token shipped as a literal `@ACCENT@` in the browser."""
        with self.assertRaises(SystemExit) as ctx:
            render("@NOPE@", {})
        self.assertIn("@NOPE@", str(ctx.exception))

    def test_error_names_every_missing_token_at_once(self):
        """Fixing them one build at a time is why these drift in the first place."""
        with self.assertRaises(SystemExit) as ctx:
            render("@A@ @B@", {})
        self.assertIn("@A@", str(ctx.exception))
        self.assertIn("@B@", str(ctx.exception))

    def test_set_overrides_supply_non_palette_tokens(self):
        self.assertEqual("myclass", render("@CLASSNAME@", {"CLASSNAME": "myclass"}))

    def test_a_set_value_may_reference_a_theme_token(self):
        """`--set DARK_SIDEBAR=@DARK_BG@` means "same as the background".

        Starlark cannot read the skin JSON, so a rule that wants to default one
        token to another has no way to express it except by passing the reference
        through. Without this the reference substitutes once and ships a literal
        `@DARK_BG@` in the stylesheet.
        """
        from tools.render_template import main
        import json, tempfile, os
        with tempfile.TemporaryDirectory() as d:
            tj = os.path.join(d, "t.json"); open(tj, "w").write(json.dumps(THEME))
            tmpl = os.path.join(d, "t.tmpl"); open(tmpl, "w").write("@SIDEBAR@")
            out = os.path.join(d, "o.css")
            main(["--template", tmpl, "--out", out, "--theme_json", tj,
                  "--set", "SIDEBAR=@DARK_BG@"])
            self.assertEqual("#000000", open(out).read())

    def test_lowercase_and_partial_markers_are_left_alone(self):
        """CSS and LaTeX both contain '@' — @media, @font-face, \\@ifundefined."""
        for text in ("@media (min-width: 40em)", "@font-face {", "email@example.com"):
            self.assertEqual(text, render(text, {}))


if __name__ == "__main__":
    unittest.main()
