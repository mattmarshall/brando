#!/usr/bin/env python3
"""brando marklib fit — model space -> pixel space, once.

Every brand's mark generator carries a `_tf()` that maps its model coordinates
onto a square canvas: flip y (model is y-up, pixels are y-down), centre the
drawing, and scale it to fill the canvas minus some optical padding. Four brands
wrote four incompatible versions of that:

    aion       (S/2) * (1 - 2*0.06) / half_extent,  centred on (0, center_y)
    fastverk   0.66 * S / sqrt(3),                  centred on (0, center_y)
    meridian   scale_frac * S,                      NOT centred
    tomato     0.80 * S / span,                     centred on a computed centroid

They are the same idea four times, and the differences are not deliberate: they
are four people independently deriving a scale factor. The consequence is that
"how much air is around the mark" is not comparable between brands and cannot be
adjusted in one place -- which matters, because optical padding is exactly the
knob you reach for when a mark reads too tight in a favicon.

`fit()` is that derivation, once. A brand supplies the numbers that are genuinely
its own -- how much padding it wants, where its optical centre sits -- and stops
owning the arithmetic.
"""
from __future__ import annotations

import dataclasses
from typing import Callable, Optional, Sequence, Tuple

Transform = Callable[[float, float], Tuple[float, float]]


def fit(
    canvas: float,
    *,
    half_extent: Optional[float] = None,
    bounds: Optional[Sequence[float]] = None,
    scale: Optional[float] = None,
    pad: float = 0.0,
    center: Optional[Tuple[float, float]] = None,
    flip_y: bool = True,
) -> Transform:
    """Build the model->pixel transform for a `canvas`-px square.

    Give exactly one of:

    * `half_extent` -- half the model-space width the mark should occupy. The
      mark is scaled so that extent fills the canvas minus `pad` on each side.
    * `bounds` -- a shapely `(minx, miny, maxx, maxy)`. The longer axis is fitted
      and, unless `center` says otherwise, the bbox centre becomes the origin.
      This is the fit-to-bounds mode; use it when the geometry decides the frame.
    * `scale` -- an explicit pixels-per-model-unit. For a brand that has already
      derived its own number and wants only the centring and y-flip shared.

    `pad` is a fraction of the FULL canvas, applied to each side: `pad=0.06` on a
    512px canvas leaves 30.7px of air left and right, and the mark spans the
    remaining 88%. (The implementation reads `(1 - 2*pad)` against the half-canvas,
    which is aion's formula verbatim, so adopting `fit` does not move aion's mark
    by a pixel.) `center` is the model-space point that lands at the canvas centre;
    it defaults to the bbox centre in `bounds` mode and to the origin otherwise.
    `flip_y=False` is for model spaces that are already y-down.
    """
    given = [n for n, v in (("half_extent", half_extent), ("bounds", bounds), ("scale", scale)) if v is not None]
    if len(given) != 1:
        raise ValueError(
            f"fit() needs exactly one of half_extent / bounds / scale; got {given or 'none'}"
        )

    if bounds is not None:
        minx, miny, maxx, maxy = bounds
        half = max(maxx - minx, maxy - miny) / 2.0
        if center is None:
            center = ((minx + maxx) / 2.0, (miny + maxy) / 2.0)
    elif half_extent is not None:
        half = float(half_extent)
    if center is None:
        center = (0.0, 0.0)

    if scale is None:
        if half <= 0:
            raise ValueError("fit(): the mark has zero extent; nothing to scale")
        scale = (canvas / 2.0) * (1.0 - 2.0 * pad) / half

    cx, cy = center
    mid = canvas / 2.0
    sy = -scale if flip_y else scale
    return lambda x, y: (mid + (x - cx) * scale, mid + (y - cy) * sy)


def spec_at(spec, canvas, *, field: str = "canvas"):
    """Clone `spec` with its canvas-size field replaced.

    The brands spell this two ways for the same operation --
    `Spec(**{**spec.__dict__, "canvas": n})` and `dataclasses.replace(spec,
    canvas=n)`. The first silently breaks on a dataclass with a non-init field or
    a `__slots__` class; both are re-typed in every rasterizer. One helper.
    """
    if dataclasses.is_dataclass(spec):
        return dataclasses.replace(spec, **{field: canvas})
    return type(spec)(**{**vars(spec), field: canvas})
