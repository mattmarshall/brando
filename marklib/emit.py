#!/usr/bin/env python3
"""brando marklib emit — the generator side of the outs contract.

`brand_svgs` and `brand_icons` compute their `outs` from `variants`/`layers`/
`sizes` and pass the same lists down as flags. This is what a generator uses to
read them, so it iterates what Bazel declared instead of carrying its own copy.

The point is not convenience. Bazel verifies that everything DECLARED was
produced; it does not verify the reverse, so a layer added to a generator but not
to the BUILD list is written and then silently discarded. Two lists, one checked
direction. Reading the list from the rule removes the second list entirely.

BACKWARDS COMPATIBLE ON PURPOSE. The pre-0.2.0 contract was `gen.py <out-dir>`
with the lists as module constants, and six brand repos still do that. Passing
defaults here lets a generator take the flags when its BUILD file starts sending
them and keep working when it does not, so a brand can adopt brando 0.2.0 in one
commit and migrate its generators in another.
"""
from __future__ import annotations

import argparse
from typing import List, NamedTuple, Optional, Sequence


class Emission(NamedTuple):
    out_dir: str
    prefix: Optional[str]
    variants: List[str]
    layers: List[str]
    sizes: List[int]
    # Which variants additionally get `.icns` and `.ico`. It has to come from the
    # rule for the same reason `variants` and `layers` do: `brand_icons` DECLARES
    # those outputs, and a rasterizer deciding for itself which variants to pack
    # is the one remaining way for the declared set and the produced set to
    # disagree — the exact drift the flags exist to remove.
    packed: List[str] = []


def parse_args(
    argv: Optional[Sequence[str]] = None,
    *,
    prefix: Optional[str] = None,
    variants: Sequence[str] = (),
    layers: Sequence[str] = (),
    sizes: Sequence[int] = (),
    packed: Sequence[str] = (),
) -> Emission:
    """Parse `<out-dir> [--prefix P] [--variant V]... [--layer L]... [--size N]...`.

    The keyword arguments are the generator's own defaults, used when the rule
    sends no flags. A generator that has migrated passes none, so the lists become
    required-by-absence: if the BUILD file stops sending them the generator emits
    nothing, which fails the build loudly rather than emitting a stale set.
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir", nargs="?", default=".")
    ap.add_argument("--prefix")
    ap.add_argument("--variant", action="append", default=[])
    ap.add_argument("--layer", action="append", default=[])
    ap.add_argument("--size", action="append", type=int, default=[])
    ap.add_argument("--packed", action="append", default=[])
    args = ap.parse_args(argv)

    return Emission(
        out_dir=args.out_dir,
        prefix=args.prefix or prefix,
        variants=list(args.variant) or list(variants),
        layers=list(args.layer) or list(layers),
        sizes=list(args.size) or list(sizes),
        packed=list(args.packed) or list(packed),
    )
