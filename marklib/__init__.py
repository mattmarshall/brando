"""brando marklib — the reusable mark-authoring library (package surface).

A brand imports the emission model and the shared transform from the package
root, and the heavier writers as submodules:

    from marklib import Canvas, Layer, geom_to_path, linear_gradient
    from marklib import fit, spec_at   # model->pixel transform; size-rebuild
    from marklib import raster         # Pillow helpers + the rasterizer driver
    from marklib import diagrams       # brandbook construction/grid/clearspace
    from marklib import iconcomposer   # .icon bundle writer
    from marklib import palette        # colour arithmetic + the contrast gate
    from marklib import tokens         # Theme -> CSS custom properties

`fit` and `spec_at` live at the root because every generator needs them and they
carry no third-party dependency. The rest stay submodules so a consumer that wants
only one of them does not pull Pillow, numpy and svgwrite to get it -- `tokens`
and `palette` in particular are stdlib-only by design, because turning a skin into
a stylesheet or checking its contrast should not require the geometry stack.

The re-export list here is load-bearing and `//marklib:surface_test` pins it: a
brand's `gen_<mark>.py` imports these names, so dropping one is a breaking change
for every brand repo, and an EMPTY __init__ is a breaking change for all of them
at once while looking like a no-op in review.
"""

from .fit import fit, spec_at  # noqa: F401
from .marklib import (  # noqa: F401
    Canvas,
    Layer,
    Transform,
    geom_to_path,
    linear_gradient,
    rounded_square,
    vertical_gradient,
)

__all__ = [
    "Canvas",
    "Layer",
    "Transform",
    "fit",
    "geom_to_path",
    "linear_gradient",
    "rounded_square",
    "spec_at",
    "vertical_gradient",
]
