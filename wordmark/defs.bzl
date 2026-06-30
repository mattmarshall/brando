"""brando brand_wordmark + brand_icons + brand_iconcomposer packaging macros.

These wire a brand's CONTENT (its rasterizer/mark-generator binaries, its fonts,
its config) to brando's generic pipeline, declaring the right `outs` so
`bazel build //...` regenerates every asset hermetically.
"""

def brand_icons(name, rasterizer, outs, visibility = None):
    """Run a brand's rasterizer py_binary (which imports @brando//marklib:raster)
    to emit a per-platform icon set into $(RULEDIR). `outs` is the exact list of
    files the rasterizer writes (PNG/.icns/.ico, per the brand's variants/sizes).
    """
    native.genrule(
        name = name,
        outs = outs,
        cmd = "$(execpath %s) $(RULEDIR)" % rasterizer,
        tools = [rasterizer],
        visibility = visibility or ["//visibility:public"],
    )

def brand_svgs(name, generator, outs, visibility = None):
    """Run a brand's mark generator py_binary (imports @brando//marklib) to emit
    the canonical layered SVGs (every variant x layer) into $(RULEDIR)."""
    native.genrule(
        name = name,
        outs = outs,
        cmd = "$(execpath %s) $(RULEDIR)" % generator,
        tools = [generator],
        visibility = visibility or ["//visibility:public"],
    )

def brand_iconcomposer(name, generator, outs, visibility = None):
    """Run a brand's Icon Composer generator py_binary (imports
    @brando//marklib:iconcomposer) to emit .icon bundles into $(RULEDIR)."""
    native.genrule(
        name = name,
        outs = outs,
        cmd = "$(execpath %s) $(RULEDIR)" % generator,
        tools = [generator],
        visibility = visibility or ["//visibility:public"],
    )

def brand_wordmark(
        name,
        config,
        semibold_ttf,
        medium_ttf,
        mark_svg,
        mark_png,
        outs,
        visibility = None):
    """Generate a brand's wordmark + mark/wordmark lockups via brando's generic
    wordmark tool.

    `config` is a JSON config label carrying the brand-content fields (word /
    tagline / palette / tracking; see @brando//wordmark:wordmark.py). The asset
    labels are passed to the tool as build-time `$(execpath ...)` paths, so the
    config needs no paths:
      * `semibold_ttf` / `medium_ttf` — the brand's wordmark + tagline faces
      * `mark_svg` / `mark_png` — the pre-rendered composite mark (e.g. a brand's
        //gen full composite SVG + //icons full PNG), composited into the lockups.
    `outs` is the wordmark/lockup file list the tool writes into $(RULEDIR).
    """
    srcs = [config, semibold_ttf, medium_ttf, mark_svg, mark_png]
    native.genrule(
        name = name,
        srcs = srcs,
        outs = outs,
        cmd = ("$(execpath @brando//wordmark:wordmark) " +
               "$(execpath %s) $(RULEDIR) " % config +
               "$(execpath %s) " % semibold_ttf +
               "$(execpath %s) " % medium_ttf +
               "$(execpath %s) " % mark_svg +
               "$(execpath %s)" % mark_png),
        tools = ["@brando//wordmark:wordmark"],
        visibility = visibility or ["//visibility:public"],
    )

def brand_office_pptx(name, config, wordmark_png, icon_dark, icon_light, out, visibility = None):
    """Generate a branded .pptx via brando's generic pptx tool."""
    native.genrule(
        name = name,
        srcs = [config, wordmark_png, icon_dark, icon_light],
        outs = [out],
        cmd = ("$(execpath @brando//office:pptx_gen) " +
               "$(execpath %s) $@ " % config +
               "$(execpath %s) " % wordmark_png +
               "$(execpath %s) " % icon_dark +
               "$(execpath %s)" % icon_light),
        tools = ["@brando//office:pptx_gen"],
        visibility = visibility or ["//visibility:public"],
    )

def brand_office_docx(name, config, icon, out, visibility = None):
    """Generate a branded .docx via brando's generic docx tool."""
    native.genrule(
        name = name,
        srcs = [config, icon],
        outs = [out],
        cmd = ("$(execpath @brando//office:docx_gen) " +
               "$(execpath %s) $@ $(execpath %s)" % (config, icon)),
        tools = ["@brando//office:docx_gen"],
        visibility = visibility or ["//visibility:public"],
    )
