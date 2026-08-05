"""Assert the JSON twin of the fixture skin agrees with the schema.

`//skins:fixture_binpb` already proves the textproto encodes against
meridian.theme.v1.Theme -- protoc rejects anything that doesn't. What protoc
cannot tell us is whether brando's OWN converter produced a JSON twin that says
the same thing, and that is where the 0.1.1 bug lived: a repeated field collapsed
to its last entry, so the binpb and the json silently disagreed and nothing
failed. The web binding reads the json; the native decoders read the binpb.

So this test checks the two shapes that have actually bitten us -- a repeated
message, and a uint32 emitted as a number rather than a string -- plus the two
fields that do not exist in the retired meridian 0.2.3 schema, which is what makes
this a gate on the schema pin and not just on the converter.
"""

import json
import os
import unittest


def _load():
    path = os.environ["FIXTURE_JSON"]
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class FixtureJson(unittest.TestCase):
    def setUp(self):
        self.theme = _load()

    def test_repeated_fonts_keeps_every_entry(self):
        """The 0.1.1 regression: repeated fields kept only the last occurrence."""
        fonts = self.theme["typography"]["fonts"]
        self.assertIsInstance(fonts, list)
        self.assertEqual(
            ["Fixture Sans", "Fixture Serif"], [f["family"] for f in fonts]
        )

    def test_display_face_survives(self):
        """Typography.display is field 7 -- absent from meridian 0.2.3."""
        self.assertEqual(
            "ui-serif, Georgia, serif", self.theme["typography"]["display"]
        )

    def test_uint32_fields_are_numbers(self):
        """proto3-JSON emits uint32 as a number; a string here breaks consumers."""
        self.assertEqual(16, self.theme["typography"]["base_size_px"])
        self.assertEqual(6, self.theme["metrics"]["radius_px"])
        self.assertIsInstance(self.theme["typography"]["base_size_px"], int)

    def test_status_roles_encode(self):
        """warning/info, which were unreachable until 2026-08-05.

        This case used to assert the OPPOSITE — that the roles were absent — and
        said so explicitly: "when 0.20.0+ is published and brando's pin moves,
        this test fails, and that failure is the prompt to add the roles". That is
        what happened. Palette.warning (13) and info (14) landed in
        meridian_schemas 0.20.0 and sat unreachable because `rels release` wrote
        five tagged versions to modules/meridian-schemas/, a path Bazel never
        reads. With them reachable, meridian's ValueTone can finally resolve
        NEEDS-ATTENTION and INFORMATIONAL instead of collapsing both to neutral.
        """
        for mode in ("light", "dark"):
            with self.subTest(mode=mode):
                self.assertIn("warning", self.theme[mode])
                self.assertIn("info", self.theme[mode])

    def test_singular_message_is_an_object(self):
        self.assertIsInstance(self.theme["metrics"], dict)


if __name__ == "__main__":
    unittest.main()
