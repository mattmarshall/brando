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
    from marklib import wordmark       # placement/fitting/lockup composition

THE GEOMETRY RE-EXPORTS ARE LAZY, AND THAT IS LOAD-BEARING.

`tokens` and `palette` are stdlib-only on purpose: turning a skin into a
stylesheet, or checking its contrast, should not require shapely, svgwrite,
Pillow and numpy. That claim was false for a while and nothing caught it — this
module used to import `.marklib` eagerly, so `import marklib.tokens` pulled
svgwrite through the package `__init__` and blew up anywhere the geometry stack
was not installed. The console found it, not the tests, because the tests run
under Bazel where every wheel is present.

PEP 562 `__getattr__` defers those imports until a geometry name is actually
touched, so the stdlib-only submodules genuinely are.
"""

from .fit import fit, spec_at  # noqa: F401  (stdlib only)

# name -> the submodule that defines it.
_LAZY = {
    "Canvas": "marklib",
    "Layer": "marklib",
    "Transform": "marklib",
    "geom_to_path": "marklib",
    "linear_gradient": "marklib",
    "rounded_square": "marklib",
    "vertical_gradient": "marklib",
}

_SUBMODULES = (
    "diagrams", "emit", "fit", "iconcomposer", "marklib",
    "palette", "raster", "tokens", "wordmark",
)

__all__ = ["fit", "spec_at"] + sorted(_LAZY)


def __getattr__(name):
    """Resolve a lazy geometry re-export, or a submodule, on first use.

    THE SUBMODULE BRANCH IS NOT OPTIONAL. `from marklib import raster` and
    `from marklib import iconcomposer` are the documented API, and defining
    `__getattr__` intercepts exactly the lookup Python uses to bind a submodule
    to its package — so without this, adding laziness silently breaks every
    `from marklib import <submodule>` here and in six brand repos.
    """
    import importlib

    module = _LAZY.get(name)
    if module is not None:
        value = getattr(importlib.import_module("." + module, __name__), name)
        globals()[name] = value  # cache, so this runs once per name
        return value

    if name in _SUBMODULES:
        value = importlib.import_module("." + name, __name__)
        globals()[name] = value
        return value

    raise AttributeError("module 'marklib' has no attribute %r" % name)


def __dir__():
    return sorted(set(__all__) | set(_SUBMODULES))
