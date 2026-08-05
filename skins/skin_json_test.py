"""Unit gate on skin_json, the textpb -> proto3-JSON converter.

The predecessor's tests existed almost entirely to pin two things a tokenizer had
to be TOLD — which fields are repeated, and which are numeric — because getting
either wrong produced a JSON twin that silently disagreed with the binpb.

skin_json still parses textproto (it must: it runs in the consumer's build and has
to stay stdlib-only), but it no longer *knows* those facts. It reads them from
`theme_schema.json`, which is derived from theme.proto and diffed by
`//skins:theme_schema_test`. So these cases check that the schema is actually
driving the parse — including that a schema saying "repeated" makes a
single occurrence a list, which is the case no tokenizer can infer from the text.
"""

import json
import os
import subprocess
import tempfile
import unittest

_SKIN_JSON = os.environ["SKIN_JSON"]
_SCHEMA = os.environ["THEME_SCHEMA"]


def _convert(textpb: str, schema_path: str = None) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "in.textpb")
        out = os.path.join(tmp, "out.json")
        with open(src, "w", encoding="utf-8") as fh:
            fh.write(textpb)
        subprocess.run(
            [_SKIN_JSON, "--schema", schema_path or _SCHEMA,
             "--textpb", src, "--out", out],
            check=True, capture_output=True, text=True,
        )
        with open(out, encoding="utf-8") as fh:
            return json.load(fh)


def _fails(textpb: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "in.textpb")
        with open(src, "w", encoding="utf-8") as fh:
            fh.write(textpb)
        proc = subprocess.run(
            [_SKIN_JSON, "--schema", _SCHEMA, "--textpb", src,
             "--out", os.path.join(tmp, "o.json")],
            capture_output=True, text=True,
        )
    if proc.returncode == 0:
        raise AssertionError("expected a failure, got success")
    return proc.stderr


class SchemaDriven(unittest.TestCase):
    def test_repeated_field_keeps_every_entry(self):
        """The 0.1.1 regression, generalized: N in, N out — for any N."""
        got = _convert(
            'typography {\n'
            '  fonts { family: "A" }\n'
            '  fonts { family: "B" }\n'
            '  fonts { family: "C" }\n'
            '}\n'
        )
        self.assertEqual(["A", "B", "C"], [f["family"] for f in got["typography"]["fonts"]])

    def test_a_single_occurrence_of_a_repeated_field_is_still_a_list(self):
        """The case NO tokenizer can infer: `fonts { }` written once looks exactly
        like a singular message. Only the schema knows, and a decoder expecting an
        array rejects a bare object."""
        got = _convert('typography { fonts { family: "Only" } }\n')
        self.assertIsInstance(got["typography"]["fonts"], list)
        self.assertEqual(1, len(got["typography"]["fonts"]))

    def test_uint32_emits_as_a_number(self):
        got = _convert("typography { base_size_px: 16 }\nmetrics { radius_px: 6 }\n")
        self.assertIsInstance(got["typography"]["base_size_px"], int)
        self.assertIsInstance(got["metrics"]["radius_px"], int)

    def test_field_names_stay_snake_case(self):
        """lowerCamelCase would silently break every renderer reading <brand>.json."""
        got = _convert('id: "t"\ndisplay_name: "T"\n')
        self.assertIn("display_name", got)
        self.assertNotIn("displayName", got)

    def test_unset_fields_are_omitted(self):
        got = _convert('id: "t"\n')
        self.assertEqual({"id": "t"}, got)

    def test_comments_and_escapes(self):
        got = _convert('# a comment\nid: "a \\"quoted\\" id"  # trailing\n')
        self.assertEqual('a "quoted" id', got["id"])

    def test_nested_message_types_are_tracked(self):
        """`bg` is valid inside light/dark and nowhere else — the parser must know
        which message it is in, not just which field names exist somewhere."""
        got = _convert('light { bg: "#FFF" }\ndark { bg: "#000" }\n')
        self.assertEqual("#FFF", got["light"]["bg"])
        self.assertEqual("#000", got["dark"]["bg"])


class LoudFailures(unittest.TestCase):
    def test_unknown_field_fails_rather_than_passing_through(self):
        """A typo used to land in the JSON and be dropped by the decoder later."""
        self.assertIn("no field", _fails('light { nope: "#FFF" }\n'))

    def test_a_field_in_the_wrong_message_fails(self):
        self.assertIn("no field", _fails('metrics { bg: "#FFF" }\n'))

    def test_duplicate_singular_field_fails(self):
        self.assertIn("more than once", _fails('id: "a"\nid: "b"\n'))

    def test_a_number_on_a_string_field_fails(self):
        self.assertIn("string", _fails("id: 5\n"))

    def test_a_quoted_string_on_a_numeric_field_fails(self):
        self.assertIn("numeric", _fails('typography { base_size_px: "16" }\n'))

    def test_a_block_on_a_scalar_field_fails(self):
        self.assertIn("not a message", _fails("id { }\n"))


if __name__ == "__main__":
    unittest.main()
