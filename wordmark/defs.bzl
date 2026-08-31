"""brando brand_wordmark + brand_icons + brand_iconcomposer packaging macros.

These wire a brand's CONTENT (its rasterizer/mark-generator binaries, its fonts,
its config) to brando's generic pipeline, declaring the right `outs` so
`bazel build //...` regenerates every asset hermetically.

WHY THESE RULES TAKE `variants` AND `layers` INSTEAD OF A LIST OF FILENAMES.

Bazel must know a genrule's outputs at loading time, and a Python generator knows
them at run time. Every brand resolved that by writing the set down twice -- a
`VARIANTS`/`LAYERS` pair in the generator, and a list comprehension over a
hand-copied pair in BUILD.bazel -- with a comment asking the next person to keep
them in step. That comment appears in SIX BUILD files across four repos, which is
a fair measure of how well it works.

The failure is one-directional and silent, which is what makes it worth fixing
rather than documenting. Bazel checks that everything DECLARED was produced, so
deleting a variant from the Python fails loudly. It does not check the reverse:
add a layer to the Python, forget the BUILD list, and the file is written into the
sandbox and then dropped on the floor. No error, no output, and the brand quietly
ships without an asset it thinks it has.

So the lists move to Starlark and are PASSED DOWN as flags. The generator iterates
what it is given rather than its own constants, which does not merely re-sync the
two copies -- it removes the second copy, so there is nothing left to drift.
"""

# Filenames are `<prefix>_<variant>.<layer>` for SVGs and
# `<prefix>_<variant>_<size>.png` for rasters. Layers carry their own extension
# ("svg", "glyph.svg", "bg.svg"), so a layer list reads as the suffixes it is.
def _svg_outs(prefix, variants, layers):
    return [
        "%s_%s.%s" % (prefix, variant, layer)
        for variant in variants
        for layer in layers
    ]

def _icon_outs(prefix, variants, sizes, packed):
    outs = [
        "%s_%s_%d.png" % (prefix, variant, size)
        for variant in variants
        for size in sizes
    ]
    for variant in packed:
        outs.append("%s_%s.icns" % (prefix, variant))
        outs.append("%s_%s.ico" % (prefix, variant))
    return outs

def _emit_args(prefix, variants = None, layers = None, sizes = None, packed = None):
    """The flags a generator reads instead of carrying its own constants."""
    args = ["--prefix %s" % prefix]
    for variant in variants or []:
        args.append("--variant %s" % variant)
    for layer in layers or []:
        args.append("--layer %s" % layer)
    for size in sizes or []:
        args.append("--size %d" % size)
    for variant in packed or []:
        args.append("--packed %s" % variant)
    return " ".join(args)

def _check_one_source_of_truth(name, outs, variants):
    if outs and variants:
        fail(
            "%s: pass either `outs` (the legacy explicit list) or " % name +
            "`variants`/`layers`, not both — two sources is the bug these rules " +
            "exist to remove.",
        )
    if not outs and not variants:
        fail("%s: needs `variants` (preferred) or `outs` (legacy)." % name)

def brand_svgs(
        name,
        generator,
        prefix = None,
        variants = None,
        layers = None,
        extra_outs = [],
        outs = None,
        visibility = None):
    """Run a brand's mark generator to emit its canonical layered SVGs.

    Preferred form: give `prefix`, `variants` and `layers`; the outs are the cross
    product and the generator is handed the same lists as flags.

    `extra_outs` is for files outside that cross product — brando's own selfbrand
    emits a `.bg.svg` for its background variants but not for its transparent one,
    which is real structure rather than an accident, and is better stated than
    forced into the grid.

    `outs` is the legacy explicit list, kept so a brand can adopt brando 0.2.0
    without migrating its generator in the same change.
    """
    _check_one_source_of_truth(name, outs, variants)
    if variants:
        outs = _svg_outs(prefix, variants, layers or []) + extra_outs
        args = " " + _emit_args(prefix, variants = variants, layers = layers)
    else:
        args = ""

    native.genrule(
        name = name,
        outs = outs,
        cmd = "$(execpath %s) $(RULEDIR)%s" % (generator, args),
        tools = [generator],
        visibility = visibility or ["//visibility:public"],
    )

# The interpreter and the schema it validates against, as `Label()` constants for
# the same reason `skins/defs.bzl` uses them: these macros run in the CALLER's
# package, and bzlmod resolves a plain-string label with the caller's repo
# mapping. Which schema validated a brand was once decided by an accident of the
# consumer's dependency graph, and that is the bug that taught this file to spell
# every external label out.
_MARK_PROGRAM = Label("//tools:mark_program")
_SKIN_JSON = Label("//skins:skin_json")
_MARK_PROGRAM_SCHEMA = Label("//proto/brando/v1:mark_program_schema.json")

def brand_mark_program(
        name,
        program,
        skin,
        prefix = None,
        variants = None,
        layers = None,
        extra_outs = [],
        canvas = None,
        visibility = None):
    """Layered SVGs from a MarkProgram — `brand_svgs`, for a mark that is data.

    IDENTICAL OUTS CONTRACT TO `brand_svgs`, deliberately. Same `variants` /
    `layers` / `prefix` attributes, same computed filenames, same flags passed
    down so the renderer iterates what Bazel declared rather than its own
    constants. A brand converting a hand-written generator to a MarkProgram
    changes which rule it calls and nothing else, and `brand_suite` can pick
    between them without its callers knowing.

    `skin` is the brand's Theme JSON — `brand_skin`'s `:<name>_json`. It is
    REQUIRED rather than optional because a MarkProgram's colours may name
    palette roles, and resolving them against a theme that was not supplied
    would mean either a missing fill or a guessed one. Both example brands
    resolve every colour this way, which is the point: the mark stops carrying a
    second copy of the palette.

    Args:
      name: target name; also the genrule producing the SVGs.
      program: the `brando.v1.MarkProgram` textproto.
      skin: the brand's Theme JSON (`brand_skin`'s `:<name>_json`).
      prefix: filename prefix, as in `brand_svgs`.
      variants: variant names the program declares.
      layers: layer suffixes, e.g. `["turnstile.svg", "svg"]`.
      extra_outs: real outputs outside the grid — the `bg.svg` a transparent
        variant legitimately does not have.
      canvas: override the program's own canvas size, in px.
      visibility: target visibility.
    """
    if not variants:
        fail("%s: needs `variants`. Unlike brand_svgs there is no legacy " % name +
             "explicit-`outs` path here, because nothing has ever called this " +
             "rule the old way and adding a second way now would be inventing " +
             "the drift the flags exist to remove.")

    # textproto -> JSON through the same stdlib parser a consumer's build uses.
    # Not a convenience: it is the gate. `skin_json` has no protobuf wheel to
    # fall back on, and a MarkProgram is by a distance the largest thing it has
    # been asked to read. A program it cannot parse is a program a brand repo
    # cannot ship, and this is where that fails — at build time, in the brand
    # that wrote it.
    json_target = "%s_json" % name
    native.genrule(
        name = json_target,
        srcs = [program, _MARK_PROGRAM_SCHEMA],
        outs = ["%s_program.json" % name],
        cmd = (
            "$(execpath %s) " % _SKIN_JSON +
            "--schema $(execpath %s) " % _MARK_PROGRAM_SCHEMA +
            "--textpb $(execpath %s) " % program +
            "--out $@"
        ),
        tools = [_SKIN_JSON],
        visibility = visibility or ["//visibility:public"],
    )

    args = " " + _emit_args(prefix, variants = variants, layers = layers)
    if canvas:
        args += " --canvas %d" % canvas

    native.genrule(
        name = name,
        srcs = [":%s" % json_target, skin],
        outs = _svg_outs(prefix, variants, layers or []) + extra_outs,
        cmd = (
            "$(execpath %s) $(RULEDIR)" % _MARK_PROGRAM +
            " --program $(execpath :%s)" % json_target +
            " --theme $(execpath %s)" % skin +
            args
        ),
        tools = [_MARK_PROGRAM],
        visibility = visibility or ["//visibility:public"],
    )

def brand_icons(
        name,
        rasterizer,
        prefix = None,
        variants = None,
        sizes = None,
        packed = [],
        extra_outs = [],
        outs = None,
        visibility = None):
    """Run a brand's rasterizer to emit its per-platform icon set.

    `packed` names the variants that additionally get `.icns` and `.ico`. It is a
    list rather than a bool because the brands genuinely differ: fastverk packs its
    dark variant and not its light one, which is a deliberate call about which
    icon a desktop actually installs.
    """
    _check_one_source_of_truth(name, outs, variants)
    if variants:
        outs = _icon_outs(prefix, variants, sizes or [], packed) + extra_outs
        args = " " + _emit_args(prefix, variants = variants, sizes = sizes, packed = packed)
    else:
        args = ""

    native.genrule(
        name = name,
        outs = outs,
        cmd = "$(execpath %s) $(RULEDIR)%s" % (rasterizer, args),
        tools = [rasterizer],
        visibility = visibility or ["//visibility:public"],
    )

def brand_iconcomposer(name, generator, outs, visibility = None):
    """Run a brand's Icon Composer generator py_binary (imports
    @brando//marklib:iconcomposer) to emit .icon bundles into $(RULEDIR).

    Still explicit-`outs` only: an `.icon` is a DIRECTORY of a manifest plus one
    SVG per layer, so its output set is not a flat cross product and modelling it
    as one would be a worse lie than writing it down. Left alone until a second
    brand actually emits one — today not even fastverk, its only caller, does.
    """
    native.genrule(
        name = name,
        outs = outs,
        cmd = "$(execpath %s) $(RULEDIR)" % generator,
        tools = [generator],
        visibility = visibility or ["//visibility:public"],
    )

def brand_wordmark_glyphs(name, generator, outs, visibility = None):
    """A wordmark whose letterforms are CONSTRUCTED, not set in a typeface.

    brando's `brand_wordmark` assumes a TTF and outlines it with fontTools, which
    is right for most brands. It is wrong for a brand whose wordmark IS the mark:
    aion's `o` is the mark's ring, its `a` is that ring plus the stem, its `n` is
    the ring with the sides straightened. There is no font to outline, so aion
    hand-rolled 143 lines — about 60 of which were brando's job (glyph placement,
    fitting to a padded box, the y-flip, lockup spacing, the dark/light pair).

    Those 60 now live in `@brando//marklib:wordmark`. This rule runs a brand's own
    generator against them, exactly as `brand_svgs` runs a mark generator: brando
    owns the composition, the brand owns the letterforms.

    Use `brand_wordmark` instead when the wordmark is set in a real typeface.
    """
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
    wordmark tool. For CONSTRUCTED letterforms, see `brand_wordmark_glyphs`.

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
