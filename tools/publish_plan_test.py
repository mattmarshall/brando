"""Gate on the publish plan.

The load-bearing property is that the `integrity` string is one Bazel will
accept and verify. Getting it subtly wrong — hex instead of base64, the wrong
prefix, a trailing newline — does not fail here; it fails in a consumer's fetch
with `Checksum was X but wanted Y`, which reads like a corrupted download rather
than a malformed pin.
"""

import base64
import hashlib
import json
import os
import tempfile
import unittest

from tools.publish_plan import main, plan, sri


def _pkg(d, data=b"a brando archive"):
    p = os.path.join(d, "leangres.brando")
    with open(p, "wb") as fh:
        fh.write(data)
    return p


class Integrity(unittest.TestCase):
    def test_sri_is_base64_of_the_raw_digest_not_the_hex(self):
        """The mistake that produces a plausible-looking, useless pin."""
        data = b"x"
        digest = hashlib.sha256(data).digest()
        self.assertEqual("sha256-" + base64.b64encode(digest).decode(), sri(digest))
        self.assertNotIn(digest.hex(), sri(digest))

    def test_round_trips_through_base64(self):
        data = b"some bytes"
        got = sri(hashlib.sha256(data).digest())
        self.assertEqual(
            hashlib.sha256(data).hexdigest(),
            base64.b64decode(got.split("-", 1)[1]).hex(),
        )


class Key(unittest.TestCase):
    def test_key_embeds_the_content_hash(self):
        with tempfile.TemporaryDirectory() as d:
            p = plan(_pkg(d), "https://cdn.example", "brando", "leangres", "1.0")
        self.assertTrue(p["key"].startswith("brando/leangres."))
        self.assertIn(p["sha256"][:16], p["key"])

    def test_different_bytes_get_a_different_key(self):
        """A key never changes meaning, so an edge may cache it forever and a
        publish needs no CloudFront invalidation."""
        with tempfile.TemporaryDirectory() as d:
            a = plan(_pkg(d, b"one"), "https://cdn.example", "brando", "b", "")
        with tempfile.TemporaryDirectory() as d:
            b = plan(_pkg(d, b"two"), "https://cdn.example", "brando", "b", "")
        self.assertNotEqual(a["key"], b["key"])

    def test_version_is_recorded_but_not_in_the_key(self):
        """Two builds of one version can legitimately differ — a regenerated
        asset, a newer brando. A version-keyed URL would then have two meanings,
        which is the ambiguity content addressing exists to remove."""
        with tempfile.TemporaryDirectory() as d:
            p = plan(_pkg(d), "https://cdn.example", "brando", "leangres", "2.1.0")
        self.assertEqual("2.1.0", p["version"])
        self.assertNotIn("2.1.0", p["key"])

    def test_url_joins_without_a_double_slash(self):
        with tempfile.TemporaryDirectory() as d:
            p = plan(_pkg(d), "https://cdn.example/", "brando", "b", "")
        self.assertNotIn("//brando", p["url"].split("://", 1)[1])


class Snippet(unittest.TestCase):
    def test_snippet_carries_the_same_url_and_integrity_as_the_json(self):
        """The snippet is what someone actually pastes. If it drifts from the
        JSON the publisher uploads by, the pin is wrong in the only copy anyone
        reads."""
        with tempfile.TemporaryDirectory() as d:
            pkg = _pkg(d)
            j = os.path.join(d, "plan.json")
            s = os.path.join(d, "snippet.txt")
            main([
                "--package", pkg, "--base_url", "https://cdn.example",
                "--out_json", j, "--out_snippet", s,
            ])
            data = json.load(open(j, encoding="utf-8"))
            text = open(s, encoding="utf-8").read()
        self.assertIn(data["url"], text)
        self.assertIn(data["integrity"], text)
        self.assertIn('brand.from_url(', text)

    def test_brand_defaults_to_the_filename_stem(self):
        with tempfile.TemporaryDirectory() as d:
            j = os.path.join(d, "plan.json")
            main(["--package", _pkg(d), "--base_url", "https://x", "--out_json", j])
            self.assertEqual("leangres", json.load(open(j, encoding="utf-8"))["brand"])


if __name__ == "__main__":
    unittest.main()
