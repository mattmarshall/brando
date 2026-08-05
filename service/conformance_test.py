"""The Bazel path and the service path must produce identical bytes.

THIS IS THE TEST THE WHOLE SERVICE TIER RESTS ON. "One library, two drivers" is
a claim about code that is easy to make and easy to quietly break: someone adds a
tweak to the service's stylesheet, or the rule grows a flag the service does not
pass, and nothing fails. The two outputs simply drift, and the first symptom is a
site and a PDF rendering different accents.

So this compares actual artifacts. `theme.css` as produced by `brand_css` — which
runs `//marklib:theme_css` as a binary, in a genrule, in a sandbox — against
`render_core.theme_css`, called in-process. Same input, same function, and the
test asserts the same bytes.

It runs against EVERY brand in the repo rather than one fixture. A single fixture
would pass for a divergence that only shows up on a palette with a `warning` role
or a font stack containing a comma, and brando has four real brands sitting right
there.
"""

import json
import os
import unittest

from service import render_core

# brand -> (theme JSON built by brand_skin, CSS built by brand_css). Both are
# genuine rule outputs, passed in by the BUILD file.
_BRANDS = ("brando", "leangres", "citizen_sh", "resumarsh")


def _env(brand: str, suffix: str) -> str:
    key = "%s_%s" % (brand.upper(), suffix)
    path = os.environ.get(key)
    if not path:
        raise AssertionError(
            "%s is unset: the BUILD file must pass every brand's rule outputs, "
            "or this test silently checks fewer brands than it claims" % key
        )
    return path


class Conformance(unittest.TestCase):
    def _theme(self, brand):
        with open(_env(brand, "JSON"), encoding="utf-8") as fh:
            return json.load(fh)

    def test_every_brand_is_actually_checked(self):
        """Guard the guard. If the BUILD file stops passing a brand, this test
        would otherwise get quieter rather than fail — the exact way a coverage
        gate rots."""
        for brand in _BRANDS:
            self.assertTrue(os.path.exists(_env(brand, "JSON")), brand)
            self.assertTrue(os.path.exists(_env(brand, "CSS")), brand)

    def test_theme_css_is_byte_identical_to_the_rule_output(self):
        """The load-bearing assertion.

        `brand_css` runs marklib's tokens module as a BINARY in a genrule;
        `render_core.theme_css` calls the same function in-process. If those ever
        diverge, a brand's site and its LaTeX class start rendering different
        colours and nothing reports it.
        """
        for brand in _BRANDS:
            with self.subTest(brand=brand):
                with open(_env(brand, "CSS"), "rb") as fh:
                    from_rule = fh.read()
                from_service = render_core.theme_css(self._theme(brand)).encode("utf-8")
                self.assertEqual(
                    from_rule,
                    from_service,
                    "%s: the rule and the service produce different stylesheets" % brand,
                )

    def test_contrast_findings_match_the_gate(self):
        """The service must not be more forgiving than the build.

        `brand_contrast_test` fails a build on an unreadable pair. If the service
        reported fewer findings, a brand could pass a hosted critique and fail
        its own CI — and the hosted answer is the one a human would believe.
        """
        from marklib import palette

        for brand in _BRANDS:
            with self.subTest(brand=brand):
                theme = self._theme(brand)
                self.assertEqual(
                    len(palette.check_theme(theme)),
                    len(render_core.contrast(theme)),
                    "%s: the service and the gate disagree about findings" % brand,
                )

    def test_render_emits_exactly_the_requested_kinds(self):
        theme = self._theme("brando")
        out = render_core.render(theme, kinds=["ARTIFACT_KIND_THEME_CSS"])
        self.assertEqual(["theme.css"], list(out))

    def test_a_mark_is_reported_as_unrenderable_rather_than_dropped(self):
        """A service handed an arbitrary spec cannot draw a mark: the spec names
        a generator, it does not contain the drawing, and running a
        caller-supplied generator is remote code execution rather than a feature.

        Being TOLD is the whole point. Silently returning a package without the
        mark is the same shortfall the Catalog gate exists to prevent, arriving
        through a different door.
        """
        missing = render_core.unrenderable(
            ["ARTIFACT_KIND_THEME_CSS", "ARTIFACT_KIND_MARK_SVG"]
        )
        self.assertEqual(["ARTIFACT_KIND_MARK_SVG"], missing)


if __name__ == "__main__":
    unittest.main()
