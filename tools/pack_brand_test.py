"""Gate on the `.brando` packer.

Two properties are load-bearing and neither is obvious from reading the code:
identical bytes must land once however many logical names point at them, and the
archive must be byte-reproducible. The second matters because the archive is
content-addressed INSIDE — if the zip wrapper varied by clock, two builds of an
unchanged brand would hash differently and every downstream cache and pin would
churn for nothing.
"""

import hashlib
import json
import os
import tempfile
import unittest
import zipfile

from tools.pack_brand import main

SPEC = 'id: "t"\ndisplay_name: "T"\n'


def _write(d, name, data):
    p = os.path.join(d, name)
    with open(p, "wb") as fh:
        fh.write(data)
    return p


def _pack(d, assets, spec=SPEC):
    """assets: {logical: bytes}. Returns (manifest_text, archive_path)."""
    spec_path = _write(d, "spec.textproto", spec.encode())
    args = []
    for i, (logical, data) in enumerate(assets.items()):
        args += ["--asset", f"{logical}={_write(d, f'a{i}.bin', data)}"]
    manifest = os.path.join(d, "m.textpb")
    main(["manifest", "--spec", spec_path, "--out", manifest] + args)
    with open(manifest, encoding="utf-8") as fh:
        text = fh.read()
    # Stand in for the protoc step: the zip mode only needs *a* manifest blob.
    binpb = _write(d, "brand.binpb", b"\x00encoded")
    archive = os.path.join(d, "t.brando")
    main(["zip", "--manifest", binpb, "--out", archive] + args)
    return text, archive


class Manifest(unittest.TestCase):
    def test_records_hash_size_and_media_type(self):
        with tempfile.TemporaryDirectory() as d:
            text, _ = _pack(d, {"theme.json": b'{"a":1}'})
        self.assertIn('name: "theme.json"', text)
        self.assertIn("size_bytes: 7", text)
        self.assertIn(hashlib.sha256(b'{"a":1}').hexdigest(), text)

    def test_identical_bytes_share_one_blob(self):
        """A brand's flat and mono marks are routinely the same file."""
        with tempfile.TemporaryDirectory() as d:
            text, archive = _pack(d, {"a.svg": b"same", "b.svg": b"same"})
            with zipfile.ZipFile(archive) as z:
                blobs = [n for n in z.namelist() if n.startswith("assets/")]
        self.assertEqual(1, len(blobs))
        # ...but both logical names are still present and both point at it.
        self.assertIn('name: "a.svg"', text)
        self.assertIn('name: "b.svg"', text)
        self.assertEqual(2, text.count(blobs[0]))

    def test_the_spec_is_carried_whole(self):
        """A package is self-describing; a consumer never has to find the repo."""
        with tempfile.TemporaryDirectory() as d:
            text, _ = _pack(d, {"x": b"x"}, spec='id: "leangres"\n')
        self.assertIn("spec {", text)
        self.assertIn('id: "leangres"', text)

    def test_spec_digest_is_of_the_spec_not_the_archive(self):
        """Two packages with the same digest were built from the same STATED
        brand, whatever else differed about the machine that built them."""
        spec = 'id: "t"\n'
        with tempfile.TemporaryDirectory() as d:
            a, _ = _pack(d, {"x": b"one"}, spec=spec)
        with tempfile.TemporaryDirectory() as d:
            b, _ = _pack(d, {"x": b"two"}, spec=spec)
        digest = hashlib.sha256(spec.encode()).hexdigest()
        self.assertIn(digest, a)
        self.assertIn(digest, b)

    def test_metadata_round_trips(self):
        with tempfile.TemporaryDirectory() as d:
            spec_path = _write(d, "s.textproto", SPEC.encode())
            asset = _write(d, "i.png", b"png")
            out = os.path.join(d, "m.textpb")
            main(["manifest", "--spec", spec_path, "--out", out, "--asset",
                  f"icon-512.png={asset};kind=ARTIFACT_KIND_MARK_PNG;size_px=512;mode=dark"])
            text = open(out, encoding="utf-8").read()
        self.assertIn("kind: ARTIFACT_KIND_MARK_PNG", text)
        self.assertIn("size_px: 512", text)
        self.assertIn('mode: "dark"', text)

    def test_a_malformed_asset_fails_loudly(self):
        with tempfile.TemporaryDirectory() as d:
            spec_path = _write(d, "s.textproto", SPEC.encode())
            with self.assertRaises(SystemExit):
                main(["manifest", "--spec", spec_path, "--out",
                      os.path.join(d, "m.textpb"), "--asset", "no-equals-sign"])


class Archive(unittest.TestCase):
    def test_contains_the_manifest_and_every_blob(self):
        with tempfile.TemporaryDirectory() as d:
            _, archive = _pack(d, {"a": b"one", "b": b"two"})
            with zipfile.ZipFile(archive) as z:
                names = set(z.namelist())
        self.assertIn("brand.binpb", names)
        self.assertEqual(2, len({n for n in names if n.startswith("assets/")}))

    def test_is_byte_reproducible(self):
        """The archive is content-addressed inside; a clock-varying wrapper would
        make two builds of an unchanged brand hash differently and churn every
        downstream cache and pin for nothing."""
        digests = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as d:
                _, archive = _pack(d, {"a": b"one", "b": b"two"})
                with open(archive, "rb") as fh:
                    digests.append(hashlib.sha256(fh.read()).hexdigest())
        self.assertEqual(digests[0], digests[1])

    def test_blob_paths_match_the_manifest(self):
        """The manifest and the archive must agree about where an asset lives —
        a disagreement is undiagnosable from the consumer's side."""
        with tempfile.TemporaryDirectory() as d:
            text, archive = _pack(d, {"a.svg": b"alpha", "b.svg": b"beta"})
            with zipfile.ZipFile(archive) as z:
                blobs = {n for n in z.namelist() if n.startswith("assets/")}
        for blob in blobs:
            self.assertIn(blob, text)


if __name__ == "__main__":
    unittest.main()
