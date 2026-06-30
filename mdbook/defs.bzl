"""brando brand_mdbook_theme — a templated mdBook theme/ overlay.

Templates brando's mdBook CSS / fonts.css / head.hbs with a brand's palette +
fonts + favicon, laid out as an mdBook `theme/` dir (custom.css under theme/css,
fonts under theme/fonts, head.hbs + favicon at theme/). The result is a pure
static filegroup `:<name>` — a docs build stages it and points book.toml at
`theme/css/custom.css`. Call this from the brand's own mdbook/BUILD.bazel so the
files land under that package's `theme/`.
"""

def _sed_cmd(subs):
    parts = []
    for k, v in subs.items():
        esc = v.replace("\\", "\\\\").replace("&", "\\&").replace("|", "\\|")
        parts.append("-e 's|%s|%s|g'" % (k, esc))
    return "sed " + " ".join(parts) + " $< > $@"

def brand_mdbook_theme(
        name,
        favicon,
        medium_ttf,
        semibold_ttf,
        font_family,
        ink,
        ink2,
        cream,
        accent,
        accent2,
        tertiary,
        muted,
        code_fg_dark = "#f0c98a",
        code_fg_light = "#9a5f12",
        sidebar_dark = "#101116",
        light_bg = "#F6F2E9",
        visibility = None):
    """Emit a brand mdBook theme overlay. Colors are CSS color strings
    (with '#'). `favicon` is the brand's mark SVG; `medium_ttf`/`semibold_ttf`
    its faces; `font_family` the CSS family name (e.g. "Space Grotesk").
    """
    visibility = visibility or ["//visibility:public"]

    css_subs = {
        "@INK@": ink,
        "@INK2@": ink2,
        "@CREAM@": cream,
        "@ACCENT@": accent,
        "@ACCENT2@": accent2,
        "@TERTIARY@": tertiary,
        "@MUTED@": muted,
        "@CODE_FG_DARK@": code_fg_dark,
        "@CODE_FG_LIGHT@": code_fg_light,
        "@SIDEBAR_DARK@": sidebar_dark,
        "@LIGHT_BG@": light_bg,
    }
    native.genrule(
        name = "%s_custom_css" % name,
        srcs = ["@brando//mdbook:templates/custom.css.tmpl"],
        outs = ["theme/css/custom.css"],
        cmd = _sed_cmd(css_subs),
        visibility = visibility,
    )
    native.genrule(
        name = "%s_head_hbs" % name,
        srcs = ["@brando//mdbook:templates/head.hbs.tmpl"],
        outs = ["theme/head.hbs"],
        cmd = _sed_cmd({"@INK@": ink}),
        visibility = visibility,
    )

    # fonts.css references the faces by the names they are staged under.
    native.genrule(
        name = "%s_fonts_css" % name,
        srcs = ["@brando//mdbook:templates/fonts.css.tmpl"],
        outs = ["theme/fonts/fonts.css"],
        cmd = _sed_cmd({
            "@FONT_FAMILY@": font_family,
            "@MEDIUM_TTF@": "brand-medium.ttf",
            "@SEMIBOLD_TTF@": "brand-semibold.ttf",
        }),
        visibility = visibility,
    )

    # Stage the favicon + fonts at the expected theme/ paths. The fonts are
    # staged under brand-neutral names that fonts.css references.
    native.genrule(
        name = "%s_favicon" % name,
        srcs = [favicon],
        outs = ["theme/favicon.svg"],
        cmd = "cp $< $@",
        visibility = visibility,
    )
    native.genrule(
        name = "%s_font_medium" % name,
        srcs = [medium_ttf],
        outs = ["theme/fonts/brand-medium.ttf"],
        cmd = "cp $< $@",
        visibility = visibility,
    )
    native.genrule(
        name = "%s_font_semibold" % name,
        srcs = [semibold_ttf],
        outs = ["theme/fonts/brand-semibold.ttf"],
        cmd = "cp $< $@",
        visibility = visibility,
    )

    native.filegroup(
        name = name,
        srcs = [
            ":%s_custom_css" % name,
            ":%s_head_hbs" % name,
            ":%s_fonts_css" % name,
            ":%s_favicon" % name,
            ":%s_font_medium" % name,
            ":%s_font_semibold" % name,
        ],
        visibility = visibility,
    )
