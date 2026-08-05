#!/usr/bin/env python3
"""Gate a `.brando` manifest against its own Catalog. STDLIB ONLY.

`brando.v1.Catalog` names the artifact kinds a complete brand includes. That was
the point of adding it: "what does a brand contain" stops being "whatever someone
happened to wire up" and becomes a declaration. A declaration nothing checks is
just a comment that looks like data, and this one was already false — citizen-sh
declared `ARTIFACT_KIND_MDBOOK_THEME` and shipped a package without one, because
the mdBook theme is a directory and `brand_package` addresses single files.

That failure is the bad kind. Nothing errors: `rules_brand` generates an
`:mdbook_theme` filegroup, it is empty, the docs build produces an unstyled book,
and the first person to notice is a reader. The package asserted something and
the assertion was not tested.

So: every kind in `catalog.kinds` must appear on at least one asset. The reverse
is deliberately NOT enforced — shipping more than you declared is fine and
common, since `Catalog` states the floor rather than the ceiling.

CLI: catalog_check.py --manifest brand.json --out REPORT
"""
from __future__ import annotations

import argparse
import json
import sys


def check(manifest: dict) -> tuple[list, list]:
    """Return (missing, present) kinds. `missing` empty means conformant."""
    catalog = manifest.get("spec", {}).get("catalog", {})
    declared = list(catalog.get("kinds", []))
    present = {a.get("kind") for a in manifest.get("assets", []) if a.get("kind")}
    missing = [k for k in declared if k not in present]
    return missing, sorted(present)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", required=True, help="the package's brand.json")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    with open(args.manifest, encoding="utf-8") as fh:
        manifest = json.load(fh)

    missing, present = check(manifest)
    brand = manifest.get("spec", {}).get("id", "brand")

    if missing:
        print(
            "catalog_check: %s declares %d kind(s) its package does not contain:"
            % (brand, len(missing)),
            file=sys.stderr,
        )
        for kind in missing:
            print("  %s" % kind, file=sys.stderr)
        print(
            "\nEither add the artifact, or remove the kind from the spec's "
            "catalog. A Catalog that overstates is worse than one that is short: "
            "a consumer asking for a declared kind gets an EMPTY filegroup and no "
            "error.",
            file=sys.stderr,
        )
        return 1

    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write("%s: catalog conformant, %d kind(s) present\n" % (brand, len(present)))
        for kind in present:
            fh.write("  %s\n" % kind)
    return 0


if __name__ == "__main__":
    sys.exit(main())
