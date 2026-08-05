#!/usr/bin/env python3
"""Pack a brand's built artifacts into a `.brando` archive. STDLIB ONLY.

A `.brando` is a zip holding:

    brand.binpb          a brando.v1.BrandPackage — the typed manifest
    assets/<sha256>      every artifact, addressed by the hash of its bytes

CONTENT-ADDRESSED INSIDE, NAMED OUTSIDE. The manifest maps a stable logical name
("theme.json", "mark/aion_mark.svg") to a hash path, so identical bytes appear
once however many names point at them — a brand's flat and mono marks are often
the same file — and a consumer asks for the name, never the hash.

WHY THIS EMITS A TEXTPROTO RATHER THAN THE BINARY. Serializing a proto needs the
protobuf runtime, and requiring a wheel here would repeat the mistake 0.2.0 had
to undo in skin_json: a brand repo need not have rules_python at all. So this
writes `manifest.textpb` and the rule pipes it through `protoc --encode`, exactly
as brand_skin does for a skin. protoc then doubles as the validation gate — a
manifest that does not match brando.v1 fails the build rather than shipping.

CLI: pack_brand.py --spec S --out-manifest M --staged-dir D
                   --asset 'NAME=PATH[;kind=K][;variant=V][;size_px=N][;mode=M]'...
"""
from __future__ import annotations

import argparse
import hashlib
import mimetypes
import os
import shutil
import sys
from typing import Dict, List

# Extensions the stdlib guesses wrongly or not at all.
_MEDIA = {
    ".binpb": "application/octet-stream",
    ".icns": "image/icns",
    ".ico": "image/vnd.microsoft.icon",
    ".otf": "font/otf",
    ".textpb": "text/plain",
    ".ttf": "font/ttf",
    ".woff2": "font/woff2",
}


def _media_type(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in _MEDIA:
        return _MEDIA[ext]
    guessed, _ = mimetypes.guess_type(path)
    return guessed or "application/octet-stream"


def _quote(text: str) -> str:
    return '"%s"' % text.replace("\\", "\\\\").replace('"', '\\"')


def _parse_asset(spec: str) -> Dict[str, str]:
    """`NAME=PATH[;key=value]...` -> a dict. Semicolons, because a logical name
    may contain a slash and a path may contain a comma."""
    head, _, rest = spec.partition(";")
    name, sep, path = head.partition("=")
    if not sep:
        raise SystemExit(f"pack_brand: --asset wants NAME=PATH, got {spec!r}")
    out = {"name": name, "path": path}
    for pair in filter(None, rest.split(";")):
        key, _, value = pair.partition("=")
        out[key] = value
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--spec", required=True, help="the brand's BrandSpec textproto")
    ap.add_argument("--out_manifest", required=True)
    ap.add_argument("--staged_dir", required=True, help="where assets/<sha> is written")
    ap.add_argument("--asset", action="append", default=[])
    ap.add_argument("--brando_version", default="")
    ap.add_argument("--source_repo", default="")
    ap.add_argument("--source_commit", default="")
    args = ap.parse_args(argv)

    assets_dir = os.path.join(args.staged_dir, "assets")
    os.makedirs(assets_dir, exist_ok=True)

    entries: List[str] = []
    seen = set()
    for raw in args.asset:
        a = _parse_asset(raw)
        with open(a["path"], "rb") as fh:
            data = fh.read()
        digest = hashlib.sha256(data).hexdigest()
        if digest not in seen:
            # Deliberately NOT a copy per logical name: identical bytes land once.
            with open(os.path.join(assets_dir, digest), "wb") as fh:
                fh.write(data)
            seen.add(digest)

        fields = [
            "    name: %s" % _quote(a["name"]),
            "    path: %s" % _quote("assets/" + digest),
            "    media_type: %s" % _quote(_media_type(a["path"])),
            "    size_bytes: %d" % len(data),
            "    sha256: %s" % _quote(digest),
        ]
        if a.get("kind"):
            fields.append("    kind: %s" % a["kind"])
        if a.get("variant"):
            fields.append("    variant: %s" % _quote(a["variant"]))
        if a.get("size_px"):
            fields.append("    size_px: %s" % a["size_px"])
        if a.get("mode"):
            fields.append("    mode: %s" % _quote(a["mode"]))
        entries.append("  assets {\n" + "\n".join(fields) + "\n  }")

    with open(args.spec, encoding="utf-8") as fh:
        spec_text = fh.read()
    # Nest the brand's own spec under `spec { ... }`, indented. Textproto is
    # whitespace-insensitive, so indenting is cosmetic — but a manifest a human
    # may open should read as one document.
    spec_block = "\n".join(
        ("    " + line) if line.strip() else line for line in spec_text.splitlines()
    )

    digest_of_spec = hashlib.sha256(spec_text.encode("utf-8")).hexdigest()
    provenance = [
        "  provenance {",
        "    brando_version: %s" % _quote(args.brando_version),
        # The digest is of the SPEC, not of the archive: two packages with the
        # same digest were built from the same stated brand, whatever else
        # differed about the machine that built them.
        "    spec_digest: %s" % _quote(digest_of_spec),
    ]
    if args.source_repo:
        provenance.append("    source_repo: %s" % _quote(args.source_repo))
    if args.source_commit:
        provenance.append("    source_commit: %s" % _quote(args.source_commit))
    provenance.append("  }")

    manifest = "\n".join(
        ["spec {", spec_block, "}"] + entries + provenance
    ) + "\n"
    with open(args.out_manifest, "w", encoding="utf-8") as fh:
        fh.write(manifest)

    print("pack_brand: %d asset(s), %d unique blob(s)" % (len(args.asset), len(seen)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
