"""`brand_suite` — a whole brand from a skin and a mark generator.

WHY THIS EXISTS. `fastverk/brand` produces seventeen artifact types. `graph` and
`savault` produce two. Every other brand in the fleet is a strict subset of
fastverk — not because those brands wanted less, but because each one was wired
up by hand from the same rules in a different order, and stopped wherever its
author stopped. A new brand therefore starts at two artifacts and grows by
copy-paste from whichever existing brand someone happens to open.

So the asymmetry is the bug: a brand should start complete. `brand_suite` names
the catalog once, and a brand opts OUT of what it does not want rather than
opting in to each thing it does. `//selfbrand` was 298 lines of BUILD; the same
brand through this macro is under 30.

WHAT IT IS NOT. It is not a new layer of abstraction over the rules — it calls
exactly the rules a brand would call by hand, with the same attributes, and every
target it makes is nameable and overridable. A brand that needs something unusual
drops the macro for that one artifact and keeps it for the rest.
"""

load("//doc:defs.bzl", "brand_latex_class")
load("//mdbook:defs.bzl", "brand_mdbook_theme")
load("//pkg:defs.bzl", "brand_package", "brand_publish_plan")
load("//skins:defs.bzl", "brand_skin")
load("//wordmark:defs.bzl", "brand_icons", "brand_svgs")

_THEME_CSS = Label("//marklib:theme_css")
_CONTRAST = Label("//marklib:contrast")
_MEDIUM_TTF = Label("//fonts:space_grotesk_medium")
_SEMIBOLD_TTF = Label("//fonts:space_grotesk_semibold")

def brand_css(name, skin, prefix = "brand", selector = ":root", visibility = None):
    """Theme -> CSS custom properties, as a standalone artifact.

    The projection already existed inside `brand_mdbook_theme`, which meant the
    only way to get a brand's stylesheet was to also want an mdBook. Three
    TypeScript files in this fleet hardcode a palette; this is what they should
    import instead.
    """
    native.genrule(
        name = name,
        srcs = [skin],
        outs = ["%s.css" % name],
        cmd = (
            "$(execpath %s) " % _THEME_CSS +
            "--theme_json $(execpath %s) " % skin +
            "--prefix %s --selector '%s' --out $@" % (prefix, selector)
        ),
        tools = [_THEME_CSS],
        visibility = visibility or ["//visibility:public"],
    )

def brand_contrast_test(name, skin, allow = None, visibility = None):
    """Fail the build when a role pair is unreadable.

    No brand in this fleet had any contrast checking. Run flat at WCAG AA the
    rule flagged all six skins on `border`, which is a bad rule rather than six
    bad palettes — a gate that fails everything gets disabled. So the table
    carries SEVERITY: `error` only where the usage is unambiguous (`fg`, `muted`
    and `code_fg` are text and nothing else; `on_accent` is defined as text on an
    accent fill), `warn` where a role is rendered more than one way.

    `allow` waives one pair, e.g. `dark:muted/surface`. A waiver is a decision
    and belongs in the BUILD file next to a reason — which is why it is not a
    threshold knob on the checker.
    """
    native.genrule(
        name = name,
        srcs = [skin],
        outs = ["%s.txt" % name],
        cmd = (
            "$(execpath %s) " % _CONTRAST +
            "--theme_json $(execpath %s) " % skin +
            " ".join(["--allow %s" % a for a in (allow or [])]) +
            " > $@"
        ),
        tools = [_CONTRAST],
        visibility = visibility or ["//visibility:public"],
    )

def brand_suite(
        name,
        spec,
        skin,
        mark = None,
        rasterizer = None,
        packed = None,
        bg_variants = None,
        variants = None,
        layers = None,
        sizes = None,
        wordmark = None,
        favicon = None,
        font_family = "Space Grotesk",
        medium_ttf = None,
        semibold_ttf = None,
        bold_font = None,
        contrast_waivers = None,
        latex = True,
        latex_classname = None,
        mdbook = True,
        package = True,
        brando_version = "",
        source_repo = "",
        publish_base_url = "",
        extra_assets = None,
        visibility = None):
    """Instantiate a brand's full catalog.

    Args:
      name: the brand id. Targets are `:<name>_skin`, `:<name>_css`, and so on.
      spec: the brand's `brando.v1.BrandSpec` textproto — identity, positioning,
        voice, font provenance. This is what a human or a model authors.
      skin: the brand's `meridian.theme.v1.Theme` textproto.

        These are two files today because `brand_skin` encodes a Theme and a
        BrandSpec merely CONTAINS one (field 4). Deriving the skin from the spec
        needs a tool that can extract a nested message from a textproto without a
        protobuf runtime in the consumer, which is a real piece of work and not
        this macro's job. Until then, authoring both is honest; conflating them
        would silently encode the wrong message.
      rasterizer: the `py_binary` emitting PNG icons. Separate from `mark`
        because the two produce different artifact kinds from one geometry — it
        should IMPORT the generator rather than redraw the mark, which is what
        five brands in this fleet did, invisibly.
      mark: a `py_binary` drawing the mark, written against `marklib`. Optional:
        a brand may legitimately be type-only before its mark exists, and this
        should not block it from having a theme, a stylesheet and a package.
      variants: mark variants (e.g. `["flat", "mono", "inkbg"]`).
      layers: layer names the generator emits per variant. Do NOT list `bg.svg`
        here — see `bg_variants`.
      bg_variants: the variants that have a background. A background layer is
        real structure rather than an exception to paper over: `transparent` has
        none, and the variants x layers grid would otherwise declare a
        `transparent.bg.svg` the generator correctly never writes. Defaults to
        every variant except one literally named `transparent`.
      sizes: PNG sizes to rasterize.
      wordmark: an optional `filegroup`/target of wordmark artifacts.
      packed: variants that additionally get `.icns` and `.ico`. Defaults to the
        primary variant, because an mdBook theme needs a favicon and `.ico` is
        the only artifact that is one. A list rather than a bool because brands
        genuinely differ about which icon a desktop should install.
      favicon: the `.ico` for the mdBook theme. Defaults to the primary variant's,
        which is why `packed` defaults as it does. With no rasterizer at all the
        mdBook theme is skipped rather than failed — a brand with no mark yet
        still wants its stylesheet, its LaTeX class and its package.
      font_family/medium_ttf/semibold_ttf: the web font. Defaults to brando's
        shared Space Grotesk, which is what every brand in the fleet already
        ships — byte-identical, three times over, ~530 KB duplicated.
      bold_font: the bold face name for LaTeX. Defaults to `<font_family>
        SemiBold`, matching the weight brando's shared fonts actually ship — a
        class asking for a Bold that is not in the package falls back silently,
        which is the failure `aion/brand/fonts/README.md` documents.
      latex_classname: the `\\documentclass` name. Defaults to the brand id.
      publish_base_url: when set, also emit the publish plan — the
        content-addressed URL and the SRI `integrity` a consumer must pin. Worth
        having by default: `rules_brand.from_url` requires the integrity, and
        computing it by hand is the step people skip. An unpinned brand means a
        CDN object swap restyles every consumer at once, silently.
      contrast_waivers: pairs to waive, e.g. `["light:muted/bg"]`. Put the reason
        beside it; a waiver is a design decision, not a threshold.
      latex/mdbook/package: opt OUT of parts of the catalog.
      extra_assets: additional `{logical_name: label_or_dict}` for the package —
        anything brand-specific that the standard catalog does not name.
    """
    visibility = visibility or ["//visibility:public"]

    brand_skin(
        name = "%s_skin" % name,
        textpb = skin,
        visibility = visibility,
    )
    skin_json = ":%s_skin_json" % name

    brand_css(
        name = "%s_css" % name,
        skin = skin_json,
        visibility = visibility,
    )

    brand_contrast_test(
        name = "%s_contrast" % name,
        skin = skin_json,
        allow = contrast_waivers,
        visibility = visibility,
    )

    assets = {
        "theme.binpb": {
            "label": ":%s_skin_binpb" % name,
            "kind": "ARTIFACT_KIND_THEME_BINPB",
        },
        "theme.json": {
            "label": skin_json,
            "kind": "ARTIFACT_KIND_THEME_JSON",
        },
        "theme.css": {
            "label": ":%s_css" % name,
            "kind": "ARTIFACT_KIND_THEME_CSS",
        },
    }

    primary = (variants or ["flat"])[0]

    if mark:
        bg = bg_variants if bg_variants != None else [
            v for v in (variants or []) if v != "transparent"
        ]
        brand_svgs(
            name = "%s_svgs" % name,
            generator = mark,
            variants = variants,
            layers = layers,
            extra_outs = ["%s_%s.bg.svg" % (name, v) for v in bg],
            prefix = name,
            visibility = visibility,
        )
        packed = packed if packed != None else [primary]
        if rasterizer:
            brand_icons(
                name = "%s_icons" % name,
                rasterizer = rasterizer,
                variants = variants,
                sizes = sizes,
                packed = packed,
                prefix = name,
                visibility = visibility,
            )
            for variant in packed:
                assets["favicon-%s.ico" % variant] = {
                    "label": "%s_%s.ico" % (name, variant),
                    "kind": "ARTIFACT_KIND_FAVICON",
                    "variant": variant,
                }

        # The composed mark of the FIRST variant is the brand's mark, by
        # convention — a brand lists its primary treatment first. Naming it
        # `mark.svg` in the package is what lets a consumer ask for "the mark"
        # without knowing this brand's variant vocabulary.
        assets["mark.svg"] = {
            "label": "%s_%s.svg" % (name, primary),
            "kind": "ARTIFACT_KIND_MARK_SVG",
            "variant": primary,
        }
        for variant in (variants or [])[1:]:
            assets["mark-%s.svg" % variant] = {
                "label": "%s_%s.svg" % (name, variant),
                "kind": "ARTIFACT_KIND_MARK_SVG",
                "variant": variant,
            }
        for size in (sizes or []) if rasterizer else []:
            assets["icon-%d.png" % size] = {
                "label": "%s_%s_%d.png" % (name, primary, size),
                "kind": "ARTIFACT_KIND_MARK_PNG",
                "size_px": size,
                "variant": primary,
            }

    if wordmark:
        assets["wordmark.svg"] = {
            "label": wordmark,
            "kind": "ARTIFACT_KIND_WORDMARK",
        }

    # An mdBook theme needs a favicon, so a brand with no mark cannot have one
    # yet. Skipping is the right failure: it should not block the theme, the
    # stylesheet, the LaTeX class or the package, all of which are mark-free.
    if mdbook and (favicon or rasterizer):
        brand_mdbook_theme(
            name = "%s_mdbook" % name,
            skin = skin_json,
            favicon = favicon or "%s_%s.ico" % (name, primary),
            medium_ttf = medium_ttf or _MEDIUM_TTF,
            semibold_ttf = semibold_ttf or _SEMIBOLD_TTF,
            font_family = font_family,
            theme_dir = "%s_mdbook_theme" % name,
            visibility = visibility,
        )

    if latex:
        classname = latex_classname or name
        brand_latex_class(
            name = "%s_latex" % name,
            skin = skin_json,
            classname = classname,
            main_font = font_family,
            bold_font = bold_font or (font_family + " SemiBold"),
            visibility = visibility,
        )
        # All three emitted files, not just the article class. 0.2.0's rename
        # broke the beamer theme precisely because only one of the three was
        # exercised, and a package that carries one of three is the same mistake
        # in a different place: a consumer wanting a deck would find nothing.
        for logical, out in (
            ("latex/%s.cls" % classname, "%s.cls" % classname),
            ("latex/%s-onepager.cls" % classname, "%s-onepager.cls" % classname),
            ("latex/beamertheme%s.sty" % classname, "beamertheme%s.sty" % classname),
        ):
            assets[logical] = {
                "label": out,
                "kind": "ARTIFACT_KIND_LATEX_CLASS",
            }

    # KNOWN GAP: the mdBook theme is a DIRECTORY, and `brand_package` addresses
    # single files — content addressing needs bytes to hash. So `:<name>_mdbook`
    # is built and usable in-repo but does not travel in the archive yet. Packing
    # it means either flattening the directory into named entries or teaching the
    # packer about tree artifacts; stating the gap beats shipping a package whose
    # Catalog claims an MDBOOK_THEME it does not contain.

    for logical, value in (extra_assets or {}).items():
        assets[logical] = value

    if package:
        brand_package(
            name = "%s_package" % name,
            spec = spec,
            assets = assets,
            brando_version = brando_version,
            source_repo = source_repo,
            visibility = visibility,
        )

        if publish_base_url:
            brand_publish_plan(
                name = "%s_publish" % name,
                package = ":%s_package" % name,
                base_url = publish_base_url,
                # Explicit, because the filename stem is `<name>_package` and a
                # consumer's repo should be named for the BRAND, not the target
                # that built it.
                brand = name,
                version = brando_version,
                visibility = visibility,
            )
