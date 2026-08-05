"""brando brand_mdbook_theme — a templated mdBook theme/ overlay.

Templates brando's mdBook CSS / fonts.css / head.hbs with a brand's palette +
fonts + favicon, laid out as an mdBook `theme/` dir (custom.css under theme/css,
fonts under theme/fonts, head.hbs + favicon at theme/). The result is a pure
static filegroup `:<name>` — a docs build stages it and points book.toml at
`theme/css/custom.css`.

TWO THINGS CHANGED IN 0.2.0, BOTH FOR THE SAME REASON.

The palette now comes from `skin` rather than from eight colour attributes. Those
attributes were the third place a brand typed its palette (after the textproto and
the mark's Spec), and re-typing is how fastverk's office config ended up carrying
the light-mode accent while everything else carried dark.

And the template's tokens moved from `@INK@` / `@CREAM@` / `@TERTIARY@` to the
theme's own role names. `ink` and `cream` are fastverk's words for fastverk's
colours; a template written in them cannot honestly describe a brand whose
background is not ink, and `--fv-*` put fastverk's name in every other brand's
stylesheet. The CSS variables are now `--brand-*`.
"""

_TEMPLATES = "@brando//mdbook:templates/"
_RENDER = "@brando//tools:render_template"

def brand_mdbook_theme(
        name,
        favicon,
        medium_ttf,
        semibold_ttf,
        font_family,
        skin = None,
        theme_dir = "theme",
        sidebar = None,
        colors = None,
        overrides = {},
        visibility = None):
    """Emit a brand mdBook theme overlay.

    `skin` is a brand_skin `<name>_json` label; the palette is read from it.

    `theme_dir` is the directory the overlay lands in, defaulting to `theme` (what
    mdBook expects, and what every existing caller gets). It exists because the
    six output paths used to be hardcoded, which quietly limited a package to ONE
    theme — a brand wanting a second (a docs variant, a dark-only build) had to
    make a second package. Pass a different `theme_dir` instead.

    `sidebar` overrides the sidebar background, which has no Theme role of its own;
    it defaults to the dark background.

    `colors` is the legacy escape hatch: a dict of TOKEN -> value for a brand that
    has not yet published a skin. Prefer `skin`.

    `overrides` is different, and allowed ALONGSIDE `skin`: a dict for tokens that
    genuinely have no Theme role. mdBook has a sidebar background and a "tertiary"
    slate; `meridian.theme.v1` has neither. Forcing those onto the nearest role
    would silently restyle a brand — fastverk's tertiary is #4A565A while its
    skin's `border` is #2A2C33, which are not the same colour and were never meant
    to be. Naming the exception is honest; collapsing it is not.
    """
    visibility = visibility or ["//visibility:public"]
    if bool(skin) == bool(colors):
        fail(
            "%s: pass either `skin` (preferred) or `colors` (legacy), not both " % name +
            "— re-typing the palette next to the skin it came from is exactly " +
            "the drift `skin` removes.",
        )

    srcs = [skin] if skin else []
    theme_arg = "--theme_json $(execpath %s) " % skin if skin else ""

    def _render(rule_name, template, out, sets):
        native.genrule(
            name = rule_name,
            srcs = srcs + [_TEMPLATES + template],
            outs = [out],
            cmd = (
                "$(execpath %s) " % _RENDER +
                "--template $(execpath %s) --out $@ " % (_TEMPLATES + template) +
                theme_arg +
                # Single-quoted: values are font families ("Space Grotesk"),
                # display names and taglines, which contain spaces.
                " ".join(["--set '%s=%s'" % (k, v) for k, v in sets.items()])
            ),
            tools = [_RENDER],
            visibility = visibility,
        )

    css_sets = dict(colors or {})
    css_sets.update(overrides)

    # The sidebar is genuinely not a Theme role — mdBook has one and the contract
    # does not. Defaulting it to the dark background beats inventing a role, and
    # beats the hardcoded #101116 it used to carry.
    #
    # The default has to be resolved HERE for the legacy `colors` path, because
    # there is no skin JSON to resolve "@DARK_BG@" against in that case and the
    # renderer would fail with "no value for @DARK_BG@" — a --set value can
    # reference a THEME token, not another --set.
    if "DARK_SIDEBAR" not in css_sets:
        if sidebar:
            css_sets["DARK_SIDEBAR"] = sidebar
        elif colors:
            css_sets["DARK_SIDEBAR"] = colors.get("DARK_BG", "#101116")
        else:
            css_sets["DARK_SIDEBAR"] = "@DARK_BG@"

    _render("%s_custom_css" % name, "custom.css.tmpl",
            "%s/css/custom.css" % theme_dir, css_sets)
    head_sets = dict(colors or {})
    head_sets.update(overrides)
    _render("%s_head_hbs" % name, "head.hbs.tmpl", "%s/head.hbs" % theme_dir, head_sets)
    _render("%s_fonts_css" % name, "fonts.css.tmpl",
            "%s/fonts/fonts.css" % theme_dir, {
                "FONT_FAMILY": font_family,
                "MEDIUM_TTF": "brand-medium.ttf",
                "SEMIBOLD_TTF": "brand-semibold.ttf",
            })

    # Stage the favicon + fonts at the expected theme/ paths, under brand-neutral
    # names that fonts.css references.
    for rule_name, src, out in (
        ("%s_favicon" % name, favicon, "%s/favicon.svg" % theme_dir),
        ("%s_font_medium" % name, medium_ttf, "%s/fonts/brand-medium.ttf" % theme_dir),
        ("%s_font_semibold" % name, semibold_ttf, "%s/fonts/brand-semibold.ttf" % theme_dir),
    ):
        native.genrule(
            name = rule_name,
            srcs = [src],
            outs = [out],
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
