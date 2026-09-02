"""Drift gate: a committed schema must match the proto it was derived from.

`skin_json.py` is stdlib-only by necessity — it runs in every consumer's build,
and brand repos need not have rules_python. That means it cannot read a
descriptor set itself, so the schema is derived here and committed.

This test is what keeps "committed" from meaning "remembered". If a proto gains a
field and nobody regenerates, the JSON twin would silently lose it — the exact
0.1.1 failure — so this fails instead.

THREE SCHEMAS, ONE TEST, and `SCHEMA_KIND` is what tells them apart. It used to
be passed and ignored, which worked only because the two schemas that existed
both happened to contain `meridian.theme.v1.Typography`: the theme's by being it,
the brand package's by embedding it. `mark_program` contains no meridian type at
all and is not supposed to, so the substance check had to become per-kind — and
each kind now asserts the fields whose absence would actually cost something.
"""

import json
import os
import unittest

KIND = os.environ.get("SCHEMA_KIND", "theme")

# What to tell someone whose build just failed. Naming the wrong file is a small
# unkindness that costs a real ten minutes.
REGENERATE = {
    "theme": ("//skins:theme_schema_regenerated",
              "bazel-bin/skins/theme_schema.regenerated.json",
              "skins/theme_schema.json"),
    "brand": ("//proto/brando/v1:brand_schema_regenerated",
              "bazel-bin/proto/brando/v1/brand_schema.regenerated.json",
              "proto/brando/v1/brand_schema.json"),
    "mark_program": ("//proto/brando/v1:mark_program_schema_regenerated",
                     "bazel-bin/proto/brando/v1/mark_program_schema.regenerated.json",
                     "proto/brando/v1/mark_program_schema.json"),
}


def _committed():
    with open(os.environ["COMMITTED"], encoding="utf-8") as fh:
        return json.load(fh)


class ThemeSchema(unittest.TestCase):
    def test_committed_schema_matches_the_pinned_proto(self):
        committed = _committed()
        with open(os.environ["REGENERATED"], encoding="utf-8") as fh:
            regenerated = json.load(fh)
        target, built, committed_path = REGENERATE.get(KIND, REGENERATE["theme"])
        self.assertEqual(
            regenerated,
            committed,
            "%s is stale — the proto changed. Regenerate:\n"
            "  bazel build %s && \\\n  cp -L %s %s"
            % (committed_path, target, built, committed_path),
        )

    def test_schema_carries_the_fields_that_have_bitten_us(self):
        """A schema that parsed but described nothing would pass the diff above."""
        schema = _committed()
        messages = schema["messages"]

        if KIND in ("theme", "brand"):
            # The two fields a brand cannot ship its own faces without. Both
            # arrived in a meridian_schemas release that sat unpublished, and a
            # schema pinned before them fails the --encode gate on exactly the
            # brands that declare fonts.
            typography = messages["meridian.theme.v1.Typography"]
            self.assertTrue(typography["fonts"]["repeated"], "fonts must be repeated")
            self.assertEqual("number", typography["base_size_px"]["kind"])
            self.assertEqual("string", typography["display"]["kind"])

        if KIND == "brand":
            # int64 is the one type whose two encodings genuinely disagree —
            # bare in a textproto, a STRING in proto3-JSON — and `size_bytes` is
            # the only field in the fleet that has one.
            self.assertEqual("int64", messages["brando.v1.Asset"]["size_bytes"]["kind"])
            # A mark that is data rather than a label. If this field ever goes
            # missing from the schema, `skin_json` silently refuses to parse a
            # spec that carries one, and the brand builds without its mark.
            self.assertEqual("brando.v1.MarkProgram",
                             messages["brando.v1.MarkSpec"]["program"]["type"])

        if KIND == "mark_program":
            self.assertEqual("brando.v1.MarkProgram", schema["root"])
            self.assertNotIn(
                "meridian.theme.v1.Theme", messages,
                "a MarkProgram names theme ROLES, never a Theme; pulling the "
                "message in would mean a mark carried a copy of the palette, "
                "which is the duplication the role reference exists to remove")

            # A `Shape` is a oneof, and every form must survive into the schema:
            # `skin_json` rejects a field it cannot find, so a dropped form is a
            # brand whose mark stops parsing rather than one that renders wrong.
            shape = messages["brando.v1.Shape"]
            for form in ("rect", "poly", "ngon", "circle", "rounded_rect", "polyline",
                         "combine", "intersect", "difference", "buffer",
                         "rotate", "translate", "scale", "repeat"):
                self.assertIn(form, shape, "Shape lost its %r form" % form)

            # Tables, because a scalar cannot hold the values that are genuinely
            # tabulated -- brando's own four fingers, each with a knuckle, a
            # reach and a curl.
            param = messages["brando.v1.Param"]
            self.assertEqual("brando.v1.ExprList", param["list"]["type"])
            self.assertEqual("brando.v1.ExprTable", param["table"]["type"])
            self.assertTrue(messages["brando.v1.ExprList"]["values"]["repeated"])

            # Every buffer option, because byte parity is unforgiving about them:
            # the same brand buffers at quad_segs 24 in one place and 12 in
            # another, and shapely's defaults are neither.
            buffer_fields = messages["brando.v1.Buffer"]
            for field in ("distance", "quad_segs", "join_style", "cap_style", "mitre_limit"):
                self.assertIn(field, buffer_fields, "Buffer lost %r" % field)

            # The composite-only flag. Without it a mark cannot express a layer
            # that is drawn but has no standalone asset, which brando's own mark
            # has exactly one of.
            self.assertEqual("bool", messages["brando.v1.LayerDef"]["composite_only"]["kind"])


if __name__ == "__main__":
    unittest.main()
