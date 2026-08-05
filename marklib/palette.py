#!/usr/bin/env python3
"""brando marklib palette — colour arithmetic and the contrast gate.

Not one of the six brand repos checks contrast. That is not an oversight anyone
made deliberately; it is that there was nowhere to put the check, so a palette
was signed off by looking at it. Looking at it is exactly the method that misses
`muted` on `surface`, because the person looking has a good monitor in a bright
room and the failing pair is two greys nobody stares at.

So this module is small on purpose: relative luminance, contrast ratio, and one
table saying which role pairs a Theme actually renders as text. `check_theme`
turns that into a list of failures, and `brand_contrast_test` turns the list into
a build failure. A palette can then be wrong in a way that stops a release rather
than in a way that ships.

The thresholds are WCAG 2.1: 4.5:1 for body text (AA), 3:1 for large text and for
non-text UI boundaries (1.4.11). They are floors, not targets.
"""
from __future__ import annotations

import json
from typing import Iterable, List, NamedTuple, Optional, Tuple

# (foreground role, background role, minimum ratio, severity, what it renders)
#
# SEVERITY EXISTS BECAUSE THE FIRST VERSION OF THIS TABLE WAS WRONG, AND RUNNING IT
# SAID SO. Holding every pair to WCAG AA flagged 35 failures across all six skins,
# including `border on bg` in every single one at ~1.2:1. Six out of six failing
# one rule is not six bad palettes; it is a bad rule -- and a gate that fails
# everything is a gate someone disables, which is worse than not having one.
#
# The split is by how certain the USAGE is. A Theme role is semantic, but several
# roles are rendered more than one way and contrast requirements follow usage:
#
#   ERROR  — unambiguously text on a background. `fg`, `muted` and `code_fg` are
#            text and nothing else; `on_accent` is defined as "text/icon on an
#            accent fill". If these fail, something is unreadable. No judgement
#            needed, so these fail the build.
#   WARN   — the role's usage varies. `accent` is links (text, 4.5) but also
#            button fills (3.0 as a non-text boundary); `danger`/`success` are
#            often a status dot rather than a word; `border` under WCAG 1.4.11
#            applies to boundaries you must perceive to operate a control, not to
#            decorative table hairlines. brando cannot tell which from the Theme
#            alone, so it reports and lets the brand decide.
#
# The honest reading of the WARN tier is "look at these", not "these are broken".
CONTRAST_RULES: Tuple[Tuple[str, str, float, str, str], ...] = (
    ("fg", "bg", 4.5, "error", "body text on the canvas"),
    ("fg", "surface", 4.5, "error", "body text on a panel"),
    ("muted", "bg", 4.5, "error", "secondary/meta text on the canvas"),
    ("muted", "surface", 4.5, "error", "secondary/meta text on a panel"),
    ("code_fg", "code_bg", 4.5, "error", "code"),
    ("on_accent", "accent", 4.5, "error", "text/icon on an accent fill"),
    ("accent", "bg", 4.5, "warn", "accent as a link (text); 3:1 suffices as a fill"),
    ("danger", "bg", 4.5, "warn", "danger as text; lower is fine for a status dot"),
    ("success", "bg", 4.5, "warn", "success as text; lower is fine for a status dot"),
    ("warning", "bg", 4.5, "warn", "warning as text; lower is fine for a status dot"),
    ("info", "bg", 4.5, "warn", "info as text; lower is fine for a status dot"),
    ("border", "bg", 3.0, "warn", "border as an operable boundary (WCAG 1.4.11)"),
)


class Failure(NamedTuple):
    mode: str
    fg_role: str
    bg_role: str
    fg: str
    bg: str
    ratio: float
    minimum: float
    severity: str
    what: str

    @property
    def key(self) -> str:
        """Stable id for waiving this pair, e.g. `dark:muted/surface`."""
        return f"{self.mode}:{self.fg_role}/{self.bg_role}"

    def __str__(self) -> str:
        return (
            f"[{self.severity}] {self.key} "
            f"({self.fg} on {self.bg}) is {self.ratio:.2f}:1, "
            f"needs {self.minimum}:1 — {self.what}"
        )


def rgb(hexstr: str) -> Tuple[int, int, int]:
    """Parse `#RGB`, `#RRGGBB` or `#RRGGBBAA` (alpha ignored) to 0-255 ints."""
    h = hexstr.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) not in (6, 8):
        raise ValueError(f"not a hex colour: {hexstr!r}")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def relative_luminance(hexstr: str) -> float:
    """WCAG 2.1 relative luminance (sRGB, linearized)."""
    def channel(v: int) -> float:
        s = v / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(v) for v in rgb(hexstr))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: str, b: str) -> float:
    """WCAG contrast ratio between two colours; 1.0 (identical) to 21.0."""
    la, lb = relative_luminance(a), relative_luminance(b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def check_palette(palette: dict, mode: str, rules=CONTRAST_RULES) -> List[Failure]:
    """Failures for one palette. Roles the skin does not set are skipped.

    Skipping absent roles is deliberate: a skin that never sets `warning` is not
    failing contrast, it is not expressing that role, and a renderer falls back.
    Flagging it here would make the gate noisy enough to be turned off.
    """
    out = []
    for fg_role, bg_role, minimum, severity, what in rules:
        fg, bg = palette.get(fg_role), palette.get(bg_role)
        if not fg or not bg:
            continue
        ratio = contrast_ratio(fg, bg)
        if ratio + 1e-9 < minimum:
            out.append(
                Failure(mode, fg_role, bg_role, fg, bg, ratio, minimum, severity, what)
            )
    return out


def check_theme(theme: dict, rules=CONTRAST_RULES) -> List[Failure]:
    """Failures across every mode a Theme declares."""
    out = []
    for mode in ("light", "dark"):
        palette = theme.get(mode)
        if palette:
            out.extend(check_palette(palette, mode, rules))
    return out


def main(argv=None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="WCAG contrast gate for a skin")
    ap.add_argument("--theme_json", required=True)
    ap.add_argument(
        "--allow",
        action="append",
        default=[],
        metavar="MODE:FG_ROLE/BG_ROLE",
        help=(
            "Waive one pair, e.g. dark:muted/surface. A waiver is a decision that "
            "should carry a reason in the BUILD file, not a threshold change here."
        ),
    )
    args = ap.parse_args(argv)

    with open(args.theme_json, encoding="utf-8") as fh:
        theme = json.load(fh)

    waived = set(args.allow)
    found = [f for f in check_theme(theme) if f.key not in waived]
    errors = [f for f in found if f.severity == "error"]
    warns = [f for f in found if f.severity != "error"]
    name = theme.get("display_name") or theme.get("id") or "skin"

    for f in warns:
        print(f"  {f}", flush=True)
    for f in errors:
        print(f"  {f}", flush=True)

    if errors:
        print(
            f"{name}: {len(errors)} unreadable pair(s); {len(warns)} to review.",
            flush=True,
        )
        return 1
    if warns:
        print(f"{name}: no unreadable pairs; {len(warns)} to review.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
