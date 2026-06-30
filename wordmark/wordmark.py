#!/usr/bin/env python3
"""brando wordmark generator — a brand's wordmark + mark/wordmark lockups.

Generalized from the fastverk wordmark tool: the typeface outlining (fontTools,
so the SVG is self-contained — no font dependency at render time) and the SVG
layout are brand-neutral; the brand supplies its WORD, TAGLINE, palette, fonts,
and a pre-rendered MARK (composite SVG body + composite PNG) via a JSON config.

The mark is consumed as an opaque pre-rendered asset (the brand renders it with
its own gen_<mark>.py through marklib), so this tool needs no knowledge of any
brand's geometry.

CLI: wordmark.py <config.json> <out-dir> \
        <semibold.ttf> <medium.ttf> <mark_svg> <mark_png>

The trailing four asset paths OVERRIDE the (build-time-unknown) paths in the
config; under Bazel they are passed as `$(execpath ...)`. The config carries the
brand-content fields (text + palette + tracking):

config.json:
{
  "word": "fastverk",
  "tagline": "proven systems, built fast",
  "ink":   "#15161A",
  "cream": "#ECE7DA",
  "tagline_dark":  "#9A9488",
  "tagline_light": "#6B6660",
  "tracking": 0.012
}
"""
from __future__ import annotations

import json
import os
import re
import sys

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont


def layout(font_path, text, tracking):
    """Lay out ``text`` in the font: returns (glyph_svg_cmds_with_x, upem, asc,
    desc, width_in_font_units)."""
    f = TTFont(font_path)
    upem = f["head"].unitsPerEm
    asc, desc = f["hhea"].ascent, f["hhea"].descent
    cmap, gs, hmtx = f.getBestCmap(), f.getGlyphSet(), f["hmtx"]
    x, track, glyphs = 0.0, tracking * upem, []
    for ch in text:
        g = cmap[ord(ch)]
        pen = SVGPathPen(gs)
        gs[g].draw(pen)
        glyphs.append((pen.getCommands(), x))
        x += hmtx[g][0] + track
    return glyphs, upem, asc, desc, x - track


def text_group(glyphs, upem, asc, s, x0, y0, color):
    """A <g> of glyph outlines, baseline at y0+asc*s; scale(s,-s) maps font
    units (y-up) -> px (y-down)."""
    out = ['<g transform="translate(%.2f,%.2f) scale(%.5f,%.5f)" fill="%s">'
           % (x0, y0 + asc * s, s, -s, color)]
    out += ['<path transform="translate(%.1f,0)" d="%s"/>' % (gx, d) for d, gx in glyphs]
    out.append("</g>")
    return "".join(out)


def svg(w, h, body):
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
            'viewBox="0 0 %d %d">%s</svg>' % (w, h, w, h, body))


def _mark_inner(mark_svg_path):
    """Read a composite mark SVG and return its inner markup + (width,height) so
    we can place it inside a <g> at an arbitrary size in the lockup."""
    txt = open(mark_svg_path, "r", encoding="utf-8").read()
    vb = re.search(r'viewBox="([\d.\s]+)"', txt)
    if vb:
        _, _, vw, vh = (float(x) for x in vb.group(1).split())
    else:
        vw = vh = 1000.0
    inner = re.sub(r"^.*?<svg[^>]*>", "", txt, count=1, flags=re.DOTALL)
    inner = re.sub(r"</svg>\s*$", "", inner, flags=re.DOTALL)
    return inner, vw, vh


def _mark_group(mark_svg_path, H):
    """Place the composite mark SVG into a <g> scaled to an HxH box."""
    inner, vw, vh = _mark_inner(mark_svg_path)
    s = H / max(vw, vh)
    return '<g transform="scale(%.5f,%.5f)">%s</g>' % (s, s, inner)


def emit_wordmark(out_dir, cfg, em=240, pad=20):
    word, sb = cfg["word"], cfg["semibold_ttf"]
    glyphs, upem, asc, desc, w = layout(sb, word, cfg["tracking"])
    s = em / upem
    W, H = round(w * s + 2 * pad), round((asc - desc) * s + 2 * pad)
    ft = ImageFont.truetype(sb, em)
    for tag, color in [("dark", cfg["cream"]), ("light", cfg["ink"])]:
        open(os.path.join(out_dir, f"wordmark_{tag}.svg"), "w").write(
            svg(W, H, text_group(glyphs, upem, asc, s, pad, pad, color)))
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(img).text((pad, pad), word, font=ft, fill=color, anchor="la")
        img.save(os.path.join(out_dir, f"wordmark_{tag}.png"))
    print("wordmark %dx%d" % (W, H))


def emit_lockup(out_dir, cfg, H=320, em=176, gap=0.30, pad=16):
    word, sb = cfg["word"], cfg["semibold_ttf"]
    glyphs, upem, asc, desc, w = layout(sb, word, cfg["tracking"])
    s = em / upem
    g = gap * H
    wm_w, wm_h = w * s, (asc - desc) * s
    W = round(H + g + wm_w + pad)
    y0 = (H - wm_h) / 2
    mark = _mark_group(cfg["mark_svg"], H)
    mark_png = Image.open(cfg["mark_png"]).convert("RGBA").resize((H, H), Image.LANCZOS)
    ft = ImageFont.truetype(sb, em)
    for tag, color in [("dark", cfg["cream"]), ("light", cfg["ink"])]:
        body = mark + text_group(glyphs, upem, asc, s, H + g, y0, color)
        open(os.path.join(out_dir, f"lockup_{tag}.svg"), "w").write(svg(W, H, body))
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        img.alpha_composite(mark_png, (0, 0))
        ImageDraw.Draw(img).text((H + g, H / 2), word, font=ft, fill=color, anchor="lm")
        img.save(os.path.join(out_dir, f"lockup_{tag}.png"))
    print("lockup %dx%d" % (W, H))


def emit_lockup_tag(out_dir, cfg, H=320, em=168, tag_em=54, gap=0.30, pad=18):
    word, tagline = cfg["word"], cfg["tagline"]
    sb, md = cfg["semibold_ttf"], cfg["medium_ttf"]
    wg, wu, wa, wd, ww = layout(sb, word, cfg["tracking"])
    tg, tu, ta, td, tw = layout(md, tagline, cfg["tracking"])
    ws, ts = em / wu, tag_em / tu
    g = gap * H
    cy = H / 2
    W = round(H + g + max(ww * ws, tw * ts) + pad)
    y_wm = cy - 0.04 * H - wa * ws
    y_tag = cy + 0.05 * H
    mark = _mark_group(cfg["mark_svg"], H)
    mark_png = Image.open(cfg["mark_png"]).convert("RGBA").resize((H, H), Image.LANCZOS)
    ftw, ftt = ImageFont.truetype(sb, em), ImageFont.truetype(md, tag_em)
    for tag, wc, tc in [("dark", cfg["cream"], cfg["tagline_dark"]),
                        ("light", cfg["ink"], cfg["tagline_light"])]:
        body = (mark
                + text_group(wg, wu, wa, ws, H + g, y_wm, wc)
                + text_group(tg, tu, ta, ts, H + g, y_tag, tc))
        open(os.path.join(out_dir, f"lockup_tag_{tag}.svg"), "w").write(svg(W, H, body))
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        img.alpha_composite(mark_png, (0, 0))
        d = ImageDraw.Draw(img)
        d.text((H + g, cy - 0.04 * H), word, font=ftw, fill=wc, anchor="ls")
        d.text((H + g, cy + 0.05 * H), tagline, font=ftt, fill=tc, anchor="la")
        img.save(os.path.join(out_dir, f"lockup_tag_{tag}.png"))
    print("lockup_tag %dx%d" % (W, H))


def main(config_path, out_dir, semibold, medium, mark_svg, mark_png):
    os.makedirs(out_dir, exist_ok=True)
    cfg = json.load(open(config_path))
    cfg.setdefault("tracking", 0.012)
    cfg.setdefault("tagline_dark", "#9A9488")
    cfg.setdefault("tagline_light", "#6B6660")
    # Build-time asset paths override anything in the config.
    cfg["semibold_ttf"] = semibold
    cfg["medium_ttf"] = medium
    cfg["mark_svg"] = mark_svg
    cfg["mark_png"] = mark_png
    emit_wordmark(out_dir, cfg)
    emit_lockup(out_dir, cfg)
    emit_lockup_tag(out_dir, cfg)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6])
