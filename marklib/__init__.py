"""brando marklib — the reusable mark-authoring library (package surface).

A brand imports the emission model from the package root and the rasterizer /
Icon Composer writers as submodules:

    from marklib import Canvas, Layer, geom_to_path, vertical_gradient
    from marklib import raster        # Pillow helpers
    from marklib import iconcomposer  # .icon bundle writer
"""
from .marklib import (  # noqa: F401
    Canvas,
    Layer,
    Transform,
    geom_to_path,
    rounded_square,
    vertical_gradient,
)
