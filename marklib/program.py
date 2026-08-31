#!/usr/bin/env python3
"""brando marklib program — a MarkProgram, executed.

WHAT THIS BUYS. Until now a brand's mark was the one part of a BrandSpec that was
not in the spec: `MarkSpec.generator` names a Bazel label, and a service handed a
spec could not run it. `render_core` says why, and is right to: "executing a
caller-supplied generator is not a scoping problem, it is remote code execution."
So the logo — the artifact a brand is most identified by — sat outside the format
that exists to hold a brand.

A MarkProgram is the drawing as DATA: primitives, boolean operations, affine
transforms, and arithmetic over named parameters. Executing one is evaluation,
not execution. There is no assignment, no recursion, and no unbounded loop, so a
program from a model or off the wire is a bounded thing to run.

THIS MODULE OWNS NO EMISSION. It builds a `marklib.Canvas` and stops. Everything
after that — the layered SVGs, the composite, the gradient dispatch, the
`fill-rule: evenodd` that keeps counters from filling in — is the same `Canvas`
every hand-written generator has always used. That is deliberate and it is what
makes byte-identical output achievable rather than aspirational: the interpreter
is not a second renderer, it is a second AUTHOR calling the first renderer.

WHAT IT DOES NOT COVER, stated plainly rather than discovered later. A
construction whose SHAPE COUNT is not known until the CSG runs — tomato's `mark`
style splits its body on a tilted half-plane and emits one facet per resulting
component — is a program, not a drawing, and `MarkSpec.generator` remains the
supported path for it. Constructed letterforms are a typeface and belong to
`//marklib:wordmark` and `brand_wordmark_glyphs`. Neither is a gap to be closed
by adding operators; they are the line between data and code, and it is better
drawn than blurred.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Dict, List, Optional, Sequence

from shapely import affinity
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

from marklib import expr as _expr
# `from marklib import fit` gives the FUNCTION, not the module: marklib's package
# root re-exports `fit` eagerly (it is stdlib-only, so it costs nothing) and that
# binding shadows the submodule of the same name. Import the function directly
# and the ambiguity disappears.
from marklib.fit import fit as _fit
from marklib.marklib import Canvas

# marklib's own defaults, restated here because proto3 cannot carry them: an
# unset scalar and a zero are the same bytes, so "unset" has to mean something
# and these are what it means.
DEFAULT_CANVAS = 1024
DEFAULT_CIRCLE_SEGMENTS = 96
DEFAULT_QUAD_SEGS = 16
DEFAULT_JOIN_STYLE = 1   # round
DEFAULT_CAP_STYLE = 1    # round
DEFAULT_MITRE_LIMIT = 5.0

# The 14 Palette roles a ThemeColor may name. Listed rather than inferred so a
# typo is an error naming the roles that exist, instead of a KeyError.
PALETTE_ROLES = (
    "bg", "surface", "fg", "muted", "border", "accent", "accent_strong",
    "on_accent", "danger", "success", "code_bg", "code_fg", "warning", "info",
)


class ProgramError(ValueError):
    """A MarkProgram that does not describe a mark.

    Distinct from `expr.ExprError` (a bad expression) so a caller can tell a
    malformed formula from a structurally impossible program, and distinct from
    anything shapely raises so a geometry failure is never reported as a schema
    failure.
    """


def _get(node: dict, name: str, default=None):
    """Read a field by its proto name, tolerating proto3-JSON's camelCase.

    brando writes snake_case everywhere — `skin_json` emits it, and
    `server.py` passes `preserving_proto_field_name=True` after a package built
    with camelCase silently lost `spec.display_name`. But a generated TypeScript
    client emits camelCase by default, and a mark that renders from Bazel and
    fails from the service would be a miserable thing to debug. Accepting both
    costs one function.
    """
    if name in node:
        return node[name]
    head, *rest = name.split("_")
    camel = head + "".join(part.title() for part in rest)
    return node.get(camel, default)


# ── parameters ────────────────────────────────────────────────────────────────
def solve_params(params: Sequence[dict], env: _expr.Env) -> _expr.Env:
    """Evaluate parameters in order, each able to see the ones before it.

    ORDER IS THE FEATURE. leangres computes `mid` once from the stem and places
    both the bar and the halmos against it; restating that midpoint at each use
    is how a mark comes apart when one measurement changes. A map would lose the
    ordering, which is why `params` is a repeated message.
    """
    out = env
    for param in params or ():
        name = _get(param, "name") or ""
        if not name:
            raise ProgramError("a parameter has no name")
        if name in out.values:
            raise ProgramError("parameter %r is declared twice" % name)

        if "value" in param or "value" in (_get(param, "value") or {}) or _get(param, "value") is not None:
            value = _expr.evaluate(_get(param, "value"), out)
        elif _get(param, "list") is not None:
            value = [_expr.evaluate(v, out) for v in _get(param, "list").get("values", [])]
        elif _get(param, "table") is not None:
            value = [
                [_expr.evaluate(v, out) for v in (row.get("values", []))]
                for row in _get(param, "table").get("rows", [])
            ]
        else:
            raise ProgramError("parameter %r sets none of value/list/table" % name)

        out = out.child(**{name: value})
    return out


# ── shapes ────────────────────────────────────────────────────────────────────
class _Shapes:
    """The geometry DAG as it is built, and the bbox window expressions see."""

    def __init__(self):
        self.by_name: Dict[str, object] = {}

    def get(self, name: str):
        if name not in self.by_name:
            raise ProgramError(
                "no shape named %r (declared so far: %s)"
                % (name, ", ".join(sorted(self.by_name)) or "none"))
        return self.by_name[name]

    def bbox(self, name: str):
        geom = self.get(name)
        if geom.is_empty:
            raise ProgramError("shape %r is empty; it has no bounds to measure" % name)
        return geom.bounds


def _points(node: dict, env: _expr.Env) -> List[tuple]:
    out = []
    for point in node.get("points", []):
        out.append((_expr.evaluate(_get(point, "x", "0"), env),
                    _expr.evaluate(_get(point, "y", "0"), env)))
    return out


def _rect(node, env):
    return box(_expr.evaluate(_get(node, "x0", "0"), env),
               _expr.evaluate(_get(node, "y0", "0"), env),
               _expr.evaluate(_get(node, "x1", "0"), env),
               _expr.evaluate(_get(node, "y1", "0"), env))


def _poly(node, env):
    pts = _points(node, env)
    if len(pts) < 3:
        raise ProgramError("a polygon needs at least 3 points, got %d" % len(pts))
    return Polygon(pts)


def _ngon(node, env):
    """A regular polygon, built the way the generators build it.

    The vertex formula is `_ngon`'s from tomato, verbatim, including that the
    first vertex sits at `rot_deg` rather than at the top. Substituting a
    shapely circle here — or even the same polygon wound the other way — changes
    the emitted path, so this reproduces rather than approximates.
    """
    import math
    cx = _expr.evaluate(_get(node, "cx", "0"), env)
    cy = _expr.evaluate(_get(node, "cy", "0"), env)
    rx = _expr.evaluate(_get(node, "rx", "0"), env)
    ry = _expr.evaluate_optional(_get(node, "ry"), env, rx)
    sides = int(_expr.evaluate(_get(node, "sides", "3"), env))
    rot = math.radians(_expr.evaluate_optional(_get(node, "rot_deg"), env, 0.0))
    if sides < 3:
        raise ProgramError("an ngon needs at least 3 sides, got %d" % sides)
    return Polygon([
        (cx + rx * math.cos(rot + 2 * math.pi * i / sides),
         cy + ry * math.sin(rot + 2 * math.pi * i / sides))
        for i in range(sides)
    ])


def _circle(node, env):
    import math
    cx = _expr.evaluate(_get(node, "cx", "0"), env)
    cy = _expr.evaluate(_get(node, "cy", "0"), env)
    r = _expr.evaluate(_get(node, "r", "0"), env)
    n = int(_expr.evaluate_optional(_get(node, "segments"), env, DEFAULT_CIRCLE_SEGMENTS))
    return Polygon([
        (cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n))
        for i in range(n)
    ])


def _rounded_rect(node, env):
    r = _expr.evaluate(_get(node, "radius", "0"), env)
    quad = int(_expr.evaluate_optional(_get(node, "quad_segs"), env, DEFAULT_QUAD_SEGS))
    core = box(_expr.evaluate(_get(node, "x0", "0"), env),
               _expr.evaluate(_get(node, "y0", "0"), env),
               _expr.evaluate(_get(node, "x1", "0"), env),
               _expr.evaluate(_get(node, "y1", "0"), env))
    if r <= 0:
        return core
    # Shrink then grow, which is how a rounded rectangle keeps the OUTER
    # dimensions it was given. Buffering the full box outward would produce a
    # shape `r` larger on every side than the numbers say.
    return core.buffer(-r, join_style=2).buffer(r, join_style=1, quad_segs=quad)


def _polyline(node, env):
    pts = _points(node, env)
    if len(pts) < 2:
        raise ProgramError("a polyline needs at least 2 points, got %d" % len(pts))
    half = _expr.evaluate(_get(node, "half_width", "0"), env)
    taper = _expr.evaluate_optional(_get(node, "taper"), env, 1.0)
    return LineString(pts).buffer(
        half * taper,
        cap_style=DEFAULT_CAP_STYLE, join_style=DEFAULT_JOIN_STYLE,
        quad_segs=DEFAULT_QUAD_SEGS,
    )


def _combine(node, env, shapes, op):
    names = node.get("shapes", [])
    if not names:
        raise ProgramError("%s names no shapes" % op)
    geoms = [shapes.get(n) for n in names]
    if op == "union":
        return unary_union(geoms)
    result = geoms[0]
    for geom in geoms[1:]:
        result = result.intersection(geom)
    return result


def _difference(node, env, shapes):
    base = shapes.get(_get(node, "base", ""))
    for name in node.get("subtract", []):
        base = base.difference(shapes.get(name))
    return base


def _buffer(node, env, shapes):
    return shapes.get(_get(node, "shape", "")).buffer(
        _expr.evaluate(_get(node, "distance", "0"), env),
        quad_segs=int(_expr.evaluate_optional(_get(node, "quad_segs"), env, DEFAULT_QUAD_SEGS)),
        join_style=int(_expr.evaluate_optional(_get(node, "join_style"), env, DEFAULT_JOIN_STYLE)),
        cap_style=int(_expr.evaluate_optional(_get(node, "cap_style"), env, DEFAULT_CAP_STYLE)),
        mitre_limit=_expr.evaluate_optional(_get(node, "mitre_limit"), env, DEFAULT_MITRE_LIMIT),
    )


def _origin(node, env, default):
    point = _get(node, "origin")
    if not point:
        return default
    return (_expr.evaluate(_get(point, "x", "0"), env),
            _expr.evaluate(_get(point, "y", "0"), env))


def _rotate(node, env, shapes):
    geom = shapes.get(_get(node, "shape", ""))
    return affinity.rotate(
        geom, _expr.evaluate(_get(node, "angle_deg", "0"), env),
        origin=_origin(node, env, "center"))


def _translate(node, env, shapes):
    return affinity.translate(
        shapes.get(_get(node, "shape", "")),
        xoff=_expr.evaluate_optional(_get(node, "dx"), env, 0.0),
        yoff=_expr.evaluate_optional(_get(node, "dy"), env, 0.0))


def _scale(node, env, shapes):
    geom = shapes.get(_get(node, "shape", ""))
    sx = _expr.evaluate_optional(_get(node, "sx"), env, 1.0)
    return affinity.scale(
        geom, xfact=sx, yfact=_expr.evaluate_optional(_get(node, "sy"), env, sx),
        origin=_origin(node, env, "center"))


def _repeat(shape: dict, node: dict, env, shapes: _Shapes):
    """The body, once per instance, with the index (and optionally a row) bound.

    A COLONNADE IS ONE STATEMENT, NOT FOUR. citizen-sh spaces its columns by
    solving for the gap so that changing the count cannot leave the portico
    off-centre; `repeat` is what lets that stay solved instead of becoming four
    hand-placed boxes the moment it is written down as data.

    `over` walks a TABLE rather than a counter, for the values that genuinely are
    tabulated — brando's own four fingers, each with its own knuckle, reach and
    curl. Those are not a formula and pretending otherwise would mean losing the
    tuning.
    """
    index_var = _get(node, "index_var") or "i"
    over = _get(node, "over")

    if over:
        rows = env.values.get(over)
        if not isinstance(rows, list) or not all(isinstance(r, list) for r in rows):
            raise ProgramError("repeat over %r: not a table parameter" % over)
        count = len(rows)
    else:
        rows = None
        count = int(_expr.evaluate(_get(node, "count", "0"), env))
    if count < 0:
        raise ProgramError("repeat count is negative (%d)" % count)

    body = _get(node, "body")
    if not body:
        raise ProgramError("repeat has no body")

    name = _get(shape, "name") or ""
    separate = bool(_get(node, "separate", False))
    instances = []
    for i in range(count):
        bindings = {index_var: float(i), "n": float(count)}
        if rows is not None:
            bindings["row"] = rows[i]
        instance_env = env.child(**bindings)
        geom = _eval_shape_form(body, instance_env, shapes)
        instances.append(geom)
        if separate:
            # Addressable individually, so a fan whose blades alternate tone can
            # put them in different layers. `name.0`, `name.1`, ... rather than a
            # bracket, because a shape reference is a plain string and adding a
            # second syntax to it would mean two ways to name one thing.
            shapes.by_name["%s.%d" % (name, i)] = geom

    return unary_union(instances) if instances else Polygon()


_PRIMITIVES = {
    "rect": lambda node, env, shapes: _rect(node, env),
    "poly": lambda node, env, shapes: _poly(node, env),
    "ngon": lambda node, env, shapes: _ngon(node, env),
    "circle": lambda node, env, shapes: _circle(node, env),
    "rounded_rect": lambda node, env, shapes: _rounded_rect(node, env),
    "polyline": lambda node, env, shapes: _polyline(node, env),
    "union_of": lambda node, env, shapes: _combine(node, env, shapes, "union"),
    "intersection_of": lambda node, env, shapes: _combine(node, env, shapes, "intersection"),
    "difference_of": lambda node, env, shapes: _difference(node, env, shapes),
    "buffer": _buffer,
    "rotate": _rotate,
    "translate": _translate,
    "scale": _scale,
}


def _eval_shape_form(shape: dict, env, shapes: _Shapes):
    """Dispatch on the `form` oneof, which in a dict is 'whichever key is set'."""
    if _get(shape, "repeat") is not None:
        return _repeat(shape, _get(shape, "repeat"), env, shapes)

    present = [key for key in _PRIMITIVES if _get(shape, key) is not None]
    if len(present) != 1:
        raise ProgramError(
            "shape %r sets %d forms; exactly one is required"
            % (_get(shape, "name") or "<unnamed>", len(present)))
    key = present[0]
    return _PRIMITIVES[key](_get(shape, key), env, shapes)


def build_shapes(program: dict, env: _expr.Env) -> _Shapes:
    """Build the DAG in declaration order.

    A shape may reference only shapes declared before it. That is what makes this
    a DAG rather than a graph, and it is checked by construction: a forward
    reference finds nothing in `_Shapes` and fails with the list of names that do
    exist.
    """
    shapes = _Shapes()
    scoped = _expr.Env(env.values, shapes.bbox)
    for shape in _get(program, "shapes", []) or []:
        name = _get(shape, "name") or ""
        geom = _eval_shape_form(shape, scoped, shapes)
        if not name:
            raise ProgramError("a top-level shape has no name")
        if name in shapes.by_name:
            raise ProgramError("shape %r is declared twice" % name)
        shapes.by_name[name] = geom
    return shapes


# ── colour ────────────────────────────────────────────────────────────────────
def resolve_color(modal: Optional[dict], mode: str, theme: Optional[dict], *, what: str) -> str:
    """One `ModalColor`, in one mode, as a hex string.

    A literal is returned as written. A theme reference is looked up in the
    brand's own palette, which is the only way a mark's ground can be the same
    colour as the brand's ground and STAY the same colour when the palette moves.
    """
    if not modal:
        raise ProgramError("%s has no colour" % what)
    ref = _get(modal, mode)
    if ref is None:
        raise ProgramError("%s has no %s colour" % (what, mode))

    literal = _get(ref, "literal")
    if literal:
        return literal

    theme_ref = _get(ref, "theme")
    if not theme_ref:
        raise ProgramError("%s (%s) sets neither literal nor theme" % (what, mode))
    if theme is None:
        raise ProgramError(
            "%s (%s) names a theme role, but no theme was supplied. A program "
            "with theme references cannot be rendered on its own." % (what, mode))

    palette_mode = _get(theme_ref, "mode") or mode
    role = _get(theme_ref, "role") or ""
    if role not in PALETTE_ROLES:
        raise ProgramError("%s names role %r, which is not one of: %s"
                           % (what, role, ", ".join(PALETTE_ROLES)))
    palette = _get(theme, palette_mode) or {}
    value = _get(palette, role)
    if not value:
        raise ProgramError(
            "%s names %s.%s, which this brand's theme does not set"
            % (what, palette_mode, role))
    return value


def _gradient(layer: dict, mode: str, theme) -> Optional[dict]:
    """A `Gradient` in the shape marklib's `Canvas` already accepts.

    Returned as the dict form (`{"stops": …, "angle": …}`) rather than the legacy
    2-tuple, because the dict form covers both and `Canvas._add_shape` dispatches
    on the type it is handed.
    """
    node = _get(layer, "gradient")
    if not node:
        return None
    stops_in = node.get("stops", [])
    if len(stops_in) < 2:
        raise ProgramError("a gradient needs at least 2 stops, got %d" % len(stops_in))

    offsets = [_get(stop, "offset") or "" for stop in stops_in]
    colors = [resolve_color(_get(stop, "color"), mode, theme, what="a gradient stop")
              for stop in stops_in]
    if any(offset.strip() for offset in offsets):
        env = _expr.Env()
        stops = [(_expr.evaluate(offset or "0", env), color)
                 for offset, color in zip(offsets, colors)]
    else:
        # Every offset empty means evenly spaced, which is the flat-list form
        # `linear_gradient` already understands.
        stops = colors
    angle = _expr.evaluate_optional(_get(node, "angle_deg"), _expr.Env(), 90.0)
    return {"stops": stops, "angle": angle}


# ── the canvas ────────────────────────────────────────────────────────────────
def _variant(program: dict, name: str) -> dict:
    for variant in _get(program, "variants", []) or []:
        if _get(variant, "name") == name:
            return variant
    known = [_get(v, "name") for v in _get(program, "variants", []) or []]
    raise ProgramError("no variant named %r (this program has: %s)"
                       % (name, ", ".join(str(k) for k in known) or "none"))


def _transform(program: dict, shapes: _Shapes, env, canvas: int):
    """`marklib.fit`'s arguments, read off `FitDef`.

    The `exactly one of` check is `fit`'s own, deliberately not re-implemented
    here: a second copy of that rule is a second place for it to be wrong.
    """
    node = _get(program, "fit") or {}
    kwargs = {}

    bounds_of = _get(node, "bounds_of")
    half_extent = _get(node, "half_extent")
    scale = _get(node, "scale")
    if bounds_of:
        geom = shapes.get(bounds_of)
        if geom.is_empty:
            raise ProgramError("fit.bounds_of names %r, which is empty" % bounds_of)
        kwargs["bounds"] = geom.bounds
    if half_extent:
        kwargs["half_extent"] = _expr.evaluate(half_extent, env)
    if scale:
        kwargs["scale"] = _expr.evaluate(scale, env)

    center = _get(node, "center")
    if center:
        kwargs["center"] = (_expr.evaluate(_get(center, "x", "0"), env),
                            _expr.evaluate(_get(center, "y", "0"), env))

    return _fit(
        canvas,
        pad=_expr.evaluate_optional(_get(node, "pad"), env, 0.0),
        flip_y=not bool(_get(node, "no_flip_y", False)),
        **kwargs,
    )


def canvas_for(program: dict, variant_name: str, *,
               theme: Optional[dict] = None, canvas: Optional[int] = None) -> Canvas:
    """Build the `marklib.Canvas` for one variant of a MarkProgram.

    Everything downstream — `emit`, `render`, the rasterizer — is the Canvas API
    every hand-written generator already uses, untouched. That is the seam that
    makes this an author rather than a renderer.
    """
    variant = _variant(program, variant_name)
    mode = _get(variant, "mode") or "light"
    if mode not in ("light", "dark"):
        raise ProgramError("variant %r has mode %r; expected light or dark"
                           % (variant_name, mode))

    env = solve_params(_get(program, "params", []) or [], _expr.Env())
    # A variant's overrides are solved AFTER the base parameters and may read
    # them, so `gradient: "0"` and `bar_y: "bar_y + 2"` are both sayable.
    overrides = _get(variant, "param_overrides", []) or []
    for param in overrides:
        name = _get(param, "name")
        if name in env.values:
            del env.values[name]
    env = solve_params(overrides, env)

    size = int(canvas or _get(program, "canvas") or DEFAULT_CANVAS)
    shapes = build_shapes(program, env)
    scoped = _expr.Env(env.values, shapes.bbox)
    out = Canvas(size=size, tf=_transform(program, shapes, scoped, size))

    ground = _get(variant, "ground")
    if ground:
        round_frac = _get(program, "bg_round")
        out.add_background(
            resolve_color(ground, mode, theme, what="variant %r's ground" % variant_name),
            round_frac=(_expr.evaluate(round_frac, scoped) if round_frac else None),
        )

    for layer in _get(program, "layers", []) or []:
        name = _get(layer, "name") or ""
        if not name:
            raise ProgramError("a layer has no name")
        out.add_layer(
            name,
            shapes.get(_get(layer, "shape", "")),
            resolve_color(_get(layer, "fill"), mode, theme, what="layer %r" % name),
            gradient=_gradient(layer, mode, theme),
            blend=_get(layer, "blend") or "normal",
            opacity=_expr.evaluate_optional(_get(layer, "opacity"), scoped, 1.0),
            # Inverted relative to marklib's field so proto3's false default is
            # the ordinary case. A composite-only layer is the exception —
            # brando's own mark has exactly one, the halo separating the hand
            # from the bar — and it has no standalone asset by design.
            emit_file=not bool(_get(layer, "composite_only", False)),
        )
    return out


def variant_names(program: dict) -> List[str]:
    return [_get(v, "name") for v in _get(program, "variants", []) or []]


def emit(program: dict, out_dir: str, prefix: str, variants: Sequence[str], *,
         theme: Optional[dict] = None, canvas: Optional[int] = None) -> List[str]:
    """Write `<out_dir>/<prefix>_<variant>.*` for each variant; return the paths.

    Returning the paths rather than nothing is `raster.render_set`'s convention,
    and it is there for the same reason: a rule that declares outputs should be
    able to assert what was actually produced.
    """
    written = []
    os.makedirs(out_dir, exist_ok=True)
    for name in variants:
        base = os.path.join(out_dir, "%s_%s" % (prefix, name))
        canvas_for(program, name, theme=theme, canvas=canvas).emit(base)
        written.append(base)
    return written


def load(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def main(argv=None) -> int:
    """`program.py <out-dir> --program P.json [--theme T.json] [--prefix …] …`

    Takes the same `--variant` / `--layer` / `--size` flags `marklib.emit` parses,
    so `brand_mark_program` can pass the lists it computed its `outs` from and
    the generator iterates what the rule declared. That is the same contract
    `brand_svgs` has with a hand-written generator, and keeping it identical is
    what lets one rule replace the other without a brand noticing.
    """
    import argparse

    from marklib import emit as emit_mod

    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("out_dir", nargs="?", default=".")
    parser.add_argument("--program", required=True)
    parser.add_argument("--theme")
    parser.add_argument("--prefix")
    parser.add_argument("--variant", action="append", default=[])
    parser.add_argument("--layer", action="append", default=[])
    parser.add_argument("--size", action="append", type=int, default=[])
    parser.add_argument("--canvas", type=int)
    args = parser.parse_args(argv)

    program = load(args.program)
    theme = load(args.theme) if args.theme else None
    emission = emit_mod.Emission(
        out_dir=args.out_dir,
        prefix=args.prefix,
        variants=list(args.variant) or variant_names(program),
        layers=list(args.layer),
        sizes=list(args.size),
    )
    if not emission.prefix:
        raise SystemExit("program.py: --prefix is required")

    emit(program, emission.out_dir, emission.prefix, emission.variants,
         theme=theme, canvas=args.canvas)
    return 0


if __name__ == "__main__":
    sys.exit(main())
