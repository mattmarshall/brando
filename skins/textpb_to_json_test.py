"""Tests for the textproto -> proto3-JSON converter.

The case that matters most here is REPEATED fields. Until meridian's Theme grew
`Typography.fonts` every field in a skin was singular, so the parser's
`parent[key] = value` was indistinguishable from correct — a repeated field
simply overwrote itself and kept the last occurrence. A skin declaring three
font sources emitted one, the `binpb` (from protoc, which handles repetition)
and the `json` twin silently disagreed, and only the JSON — the artifact the WEB
consumes — lost data. Nothing failed; the fonts just did not load.
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

TOOL = Path(__file__).resolve().parent / "textpb_to_json.py"


def convert(textpb: str) -> dict:
    with TemporaryDirectory() as tmp:
        src = Path(tmp) / "skin.textpb"
        dst = Path(tmp) / "skin.json"
        src.write_text(textpb, encoding="utf-8")
        subprocess.run([sys.executable, str(TOOL), str(src), str(dst)], check=True)
        return json.loads(dst.read_text(encoding="utf-8"))


def convert_expecting_failure(textpb: str) -> str:
    with TemporaryDirectory() as tmp:
        src = Path(tmp) / "skin.textpb"
        dst = Path(tmp) / "skin.json"
        src.write_text(textpb, encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(TOOL), str(src), str(dst)],
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            raise AssertionError("expected a failure, but the conversion succeeded")
        return proc.stderr


class RepeatedFields(unittest.TestCase):
    def test_repeated_message_keeps_every_occurrence(self):
        out = convert(
            """
            typography {
              sans: "Outfit"
              fonts { family: "Outfit" weight: "100 900" }
              fonts { family: "IBM Plex Serif" weight: "600" }
              fonts { family: "IBM Plex Serif" weight: "700" }
            }
            """
        )
        fonts = out["typography"]["fonts"]
        self.assertIsInstance(fonts, list)
        self.assertEqual(len(fonts), 3)
        self.assertEqual([f["weight"] for f in fonts], ["100 900", "600", "700"])
        # sibling scalars are untouched by the accumulation
        self.assertEqual(out["typography"]["sans"], "Outfit")

    def test_repeated_field_is_a_list_even_when_written_once(self):
        # proto3-JSON represents a repeated field as an array ALWAYS; a decoder
        # expecting one rejects a bare object, so arity must not depend on how
        # many times the author happened to write the block.
        out = convert('typography { fonts { family: "Outfit" } }')
        self.assertEqual(out["typography"]["fonts"], [{"family": "Outfit"}])

    def test_repeated_field_absent_stays_absent(self):
        out = convert('typography { sans: "Outfit" }')
        self.assertNotIn("fonts", out["typography"])


class SingularFields(unittest.TestCase):
    def test_singular_message_is_an_object_not_a_list(self):
        out = convert('light { bg: "#FFFFFF" accent: "#00ADEF" }')
        self.assertEqual(out["light"], {"bg": "#FFFFFF", "accent": "#00ADEF"})

    def test_duplicate_singular_field_is_an_error_not_a_silent_overwrite(self):
        # The old behaviour kept the last value. That is exactly how the repeated
        # bug hid, so a duplicate on a non-repeated field now fails loudly.
        err = convert_expecting_failure('id: "first"\nid: "second"\n')
        self.assertIn("appears more than once", err)

    def test_uint32_fields_emit_as_numbers(self):
        out = convert("typography { base_size_px: 16 heading_weight: 600 }")
        self.assertEqual(out["typography"]["base_size_px"], 16)
        self.assertEqual(out["typography"]["heading_weight"], 600)

    def test_comments_and_escapes(self):
        out = convert(
            """
            # a comment
            typography {
              sans: "\\"Outfit\\", sans-serif"  # trailing comment
            }
            """
        )
        self.assertEqual(out["typography"]["sans"], '"Outfit", sans-serif')


if __name__ == "__main__":
    unittest.main()
