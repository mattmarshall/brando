"""Drift gate: the committed theme_schema.json must match theme.proto.

`skin_json.py` is stdlib-only by necessity — it runs in every consumer's build,
and brand repos need not have rules_python. That means it cannot read the schema
itself, so the schema is derived here and committed.

This test is what keeps "committed" from meaning "remembered". If theme.proto
gains a field and nobody regenerates, the JSON twin would silently lose it — the
exact 0.1.1 failure — so this fails instead.
"""

import json
import os
import unittest


class ThemeSchema(unittest.TestCase):
    def test_committed_schema_matches_the_pinned_proto(self):
        with open(os.environ["COMMITTED"], encoding="utf-8") as fh:
            committed = json.load(fh)
        with open(os.environ["REGENERATED"], encoding="utf-8") as fh:
            regenerated = json.load(fh)
        self.assertEqual(
            regenerated,
            committed,
            "skins/theme_schema.json is stale — theme.proto changed. Regenerate:\n"
            "  bazel build //skins:theme_schema_regenerated && \\\n"
            "  cp -L bazel-bin/skins/theme_schema.regenerated.json "
            "skins/theme_schema.json",
        )

    def test_schema_carries_the_fields_that_have_bitten_us(self):
        """A schema that parsed but described nothing would pass the diff above."""
        with open(os.environ["COMMITTED"], encoding="utf-8") as fh:
            schema = json.load(fh)
        typography = schema["messages"]["meridian.theme.v1.Typography"]
        self.assertTrue(typography["fonts"]["repeated"], "fonts must be repeated")
        self.assertEqual("number", typography["base_size_px"]["kind"])
        self.assertEqual("string", typography["display"]["kind"])


if __name__ == "__main__":
    unittest.main()
