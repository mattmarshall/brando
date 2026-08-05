#!/usr/bin/env python3
"""citizen-sh PNG icons — the same geometry as gen_mark, rasterized.

It IMPORTS `gen_mark` rather than restating the portico. Five brands in this
fleet hand-rolled a rasterizer that redrew its own mark, and the divergence that
buys is invisible: the SVG and the PNG are both plausible, and nobody compares
them. Here the shapes come from one function, so they cannot disagree.

`marklib.raster.render_set` does the supersampling and the size loop. This file
is the ~30 lines that are genuinely citizen-sh's: which variants exist, and what
ground each sits on.

CLI: raster_mark.py <out-dir> [--variants ...] [--sizes ...]
"""
import os
import sys

from marklib import emit, fit, raster as mraster

from gen_mark import INK, PAPER, VARIANTS, Spec, layers


def _tf_for(spec, px: int):
    """The model->pixel transform at `px`. Same union as gen_mark fits, so the
    SVG and the PNG frame the mark identically."""
    from shapely.ops import unary_union

    parts, _ = layers(spec, "light")
    whole = unary_union([geom for _n, geom, _f in parts])
    return fit(px, bounds=whole.bounds, pad=(1.0 - spec.fit) / 2.0)


def paint_for(variant: str):
    """Return a `paint(img, px, spec)` for one variant, as render() expects."""
    mode, ground = VARIANTS[variant]

    def paint(img, px, spec):
        # `layers` builds its transform for a 1024 canvas; at any other pixel
        # size the transform, not the geometry, is what changes — so rebuild it
        # for `px`, which render() has already scaled for supersampling.
        parts, _ = layers(spec, mode)
        tf = _tf_for(spec, px)
        if ground is not None:
            # A restrained radius, matching the skin's metrics.radius_px. Not
            # zero: a hard square reads as unfinished once a desktop masks it.
            mraster.background_rect(img, px, ground, round_frac=0.06)
        for _name, geom, fill in parts:
            mraster.paste_geom(img, px, tf, geom, fill)

    return paint


def _at_size(spec, px):
    """The Spec is in fixed model units, so it does not vary with pixel size —
    the transform does. Returning it unchanged keeps `render` from trying to
    rebuild a `canvas` field this brand does not have."""
    return spec


def main(argv=None):
    e = emit.parse_args(argv, prefix="resumarsh", variants=list(VARIANTS),
                        sizes=mraster.PNG_SIZES)
    os.makedirs(e.out_dir, exist_ok=True)
    for variant in e.variants:
        mraster.render_set(
            e.out_dir,
            "%s_%s" % (e.prefix, variant),
            Spec(),
            paint_for(variant),
            sizes=e.sizes,
            # Which variants pack comes from the RULE, which is what declared
            # the .icns/.ico outputs. A rasterizer choosing for itself is how a
            # declared output goes unwritten.
            packed=variant in e.packed,
            at_size=_at_size,
        )
        print("icons %s_%s" % (e.prefix, variant))


if __name__ == "__main__":
    sys.exit(main())
