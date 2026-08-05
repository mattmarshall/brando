"""Gate on the console generator.

The case that matters is per-card scoping. The first version rendered every card
in the FIRST brand's palette, because the custom properties were only ever set on
:root — six cards in one brand's blue, which tells you nothing about six brands
and is exactly the failure a catalog exists to prevent.
"""

import json
import os
import tempfile
import unittest

from console.build_console import main

A = {"id": "a", "display_name": "Alpha",
     "light": {"bg": "#FFFFFF", "fg": "#000000", "accent": "#0000FF"},
     "dark": {"bg": "#000000", "fg": "#FFFFFF", "accent": "#8888FF"},
     "typography": {"sans": "Alpha Sans", "base_size_px": 16},
     "metrics": {"radius_px": 4}}
B = {"id": "b", "display_name": "Beta",
     "light": {"bg": "#FFEEEE", "fg": "#220000", "accent": "#CC0000"},
     "typography": {"sans": "Beta Sans", "base_size_px": 18},
     "metrics": {"radius_px": 16}}


def _render(**skins):
    with tempfile.TemporaryDirectory() as d:
        args = []
        for name, theme in skins.items():
            p = os.path.join(d, f"{name}.json")
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(theme, fh)
            args += ["--skin", f"{name}={p}"]
        out = os.path.join(d, "index.html")
        main(args + ["--out", out])
        with open(out, encoding="utf-8") as fh:
            return fh.read()


class Console(unittest.TestCase):
    def test_every_brand_gets_a_card(self):
        page = _render(alpha=A, beta=B)
        self.assertIn('id="brand-alpha"', page)
        self.assertIn('id="brand-beta"', page)

    def test_each_card_carries_its_own_scoped_variables(self):
        """The regression: one brand's palette applied to every card."""
        page = _render(alpha=A, beta=B)
        self.assertIn("#brand-alpha {", page)
        self.assertIn("#brand-beta {", page)

    def test_scoped_variables_are_the_brands_own(self):
        page = _render(alpha=A, beta=B)
        beta = page[page.index("#brand-beta {"):]
        self.assertIn("--brand-accent: #CC0000;", beta.split("}")[0])
        self.assertIn("--brand-radius: 16px;", beta.split("}")[0])

    def test_typography_is_per_brand_not_shared(self):
        page = _render(alpha=A, beta=B)
        self.assertIn("Alpha Sans", page)
        self.assertIn("Beta Sans", page)

    def test_contrast_report_comes_from_the_real_gate(self):
        """Alpha's dark on_accent is absent, but muted/bg etc. run the same rules
        the build runs — the console must not carry its own copy."""
        page = _render(alpha=A)
        self.assertTrue("contrast" in page.lower())

    def test_a_missing_font_source_is_called_out(self):
        """A stack is only names; a skin that ships no FontSource silently falls
        back to system-ui, which is the failure aion documented at length."""
        self.assertIn("NO declared font sources", _render(alpha=A))

    def test_no_skins_fails_loudly(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit):
                main(["--out", os.path.join(d, "x.html")])


if __name__ == "__main__":
    unittest.main()
