"""brando tectonic-doc tooling — a TEMPLATED brand LaTeX class + brand_doc rule.

`brand_latex_class` templates brando's base LaTeX class / beamer theme / one-pager
class with a brand's colors + fonts, so any brand styles its docs identically by
just passing its palette. `brand_resources` bundles the generated class(es) + the
brand's fonts into a `BrandResourcesInfo`. `brand_doc` compiles a `.tex` into a
PDF (tectonic) with those resources auto-staged — a consuming doc only writes
`\\documentclass{<class>}` and references figures at workspace-relative paths.
"""

BrandResourcesInfo = provider(
    doc = "Class + font resources auto-staged into every brando tectonic doc.",
    fields = {"files": "depset of resource Files (.cls/.sty staged at cwd; fonts at fonts/)"},
)

def _brand_resources_impl(ctx):
    return [BrandResourcesInfo(files = depset(ctx.files.srcs))]

brand_resources = rule(
    implementation = _brand_resources_impl,
    attrs = {"srcs": attr.label_list(allow_files = True, mandatory = True)},
    doc = "Bundle a brand's LaTeX class(es) + fonts into a BrandResourcesInfo.",
)

def _brand_doc_impl(ctx):
    info = ctx.toolchains["@rules_tectonic//tectonic:toolchain_type"].tectonicinfo
    out = ctx.actions.declare_file(ctx.label.name + ".pdf")
    res = ctx.attr.resources[BrandResourcesInfo].files.to_list()
    doc_inputs = [ctx.file.main] + ctx.files.srcs
    main_sp = ctx.file.main.short_path
    maindir = main_sp.rsplit("/", 1)[0] if "/" in main_sp else "."
    base = ctx.file.main.basename.rsplit(".", 1)[0]

    # Stage at workspace-relative paths (figures resolve as the .tex references
    # them, e.g. ../icons/x.png), then cd into the main's dir and run tectonic —
    # which resolves includes relative to that dir. Class/style + fonts are
    # staged INTO the main's dir (the class at cwd; fonts under fonts/) so
    # \documentclass{<class>} and Path=fonts/ resolve with no author wiring.
    stage = [(f.path, f.short_path) for f in doc_inputs]
    for f in res:
        dst = "%s/%s" % (maindir, f.basename) if f.extension in ("cls", "sty") else "%s/fonts/%s" % (maindir, f.basename)
        stage.append((f.path, dst))

    lines = ["set -e", "STAGE=$(mktemp -d)", "EXEC=$(pwd)"]
    seen = {}
    for src, dst in stage:
        d = dst.rsplit("/", 1)[0] if "/" in dst else "."
        if d not in seen:
            lines.append('mkdir -p "$STAGE/%s"' % d)
            seen[d] = True
        lines.append('cp -L "$EXEC/%s" "$STAGE/%s"' % (src, dst))

    lines += [
        'TECTONIC="$EXEC/%s"' % info.tectonic.path,
        'cd "$STAGE/%s"' % maindir,
        '"$TECTONIC" -X compile --outdir . --keep-logs "%s"' % ctx.file.main.basename,
        'mv "%s.pdf" "$EXEC/%s"' % (base, out.path),
    ]
    ctx.actions.run_shell(
        command = "\n".join(lines),
        tools = [info.tectonic],
        inputs = doc_inputs + res,
        outputs = [out],
        mnemonic = "BrandDoc",
        progress_message = "Compiling brand doc %{label}",
        use_default_shell_env = True,
    )
    return [DefaultInfo(files = depset([out]))]

brand_doc = rule(
    implementation = _brand_doc_impl,
    attrs = {
        "main": attr.label(
            allow_single_file = [".tex"],
            mandatory = True,
            doc = "Top-level .tex; should use \\documentclass{<brand class>}.",
        ),
        "srcs": attr.label_list(
            allow_files = True,
            doc = "Figures + extra inputs, referenced at workspace-relative paths.",
        ),
        "resources": attr.label(
            providers = [BrandResourcesInfo],
            mandatory = True,
            doc = "The brand class(es) + fonts bundle (a brand_resources target).",
        ),
    },
    toolchains = ["@rules_tectonic//tectonic:toolchain_type"],
    doc = "Compile a .tex into a PDF with the brand class + fonts auto-bundled.",
)

def brand_latex_class(
        name,
        classname,
        bg,
        fg,
        accent,
        tertiary,
        main_font,
        bold_font,
        wordmark = None,
        visibility = None):
    """Template brando's base LaTeX class + beamer theme + one-pager class with a
    brand's palette + fonts, and emit them with the brand's class name.

    Produces three generated files (label `:<name>` is a filegroup of all three):
      * `<classname>.cls`              — the article-based brand class
      * `beamertheme<classname>.sty`   — the beamer theme (\\usetheme{<classname>})
      * `<classname>-onepager.cls`     — the tight one-page class

    Colors are 6-hex strings WITHOUT a leading '#'. `main_font` / `bold_font` are
    the font filenames as staged under fonts/ (e.g. "MyFont-Medium.ttf").
    """
    wordmark = wordmark or classname
    subs = {
        "@CLASSNAME@": classname,
        "@BG@": bg,
        "@FG@": fg,
        "@ACCENT@": accent,
        "@TERTIARY@": tertiary,
        "@MAINFONT@": main_font,
        "@BOLDFONT@": bold_font,
        "@WORDMARK@": wordmark,
    }
    outs = [
        ("@brando//doc:templates/brand.cls.tmpl", "%s.cls" % classname),
        ("@brando//doc:templates/brand-beamer.sty.tmpl", "beamertheme%s.sty" % classname),
        ("@brando//doc:templates/brand-onepager.cls.tmpl", "%s-onepager.cls" % classname),
    ]
    out_files = []
    for tmpl, outfile in outs:
        rule_name = "%s_%s" % (name, outfile.replace(".", "_").replace("-", "_"))
        native.genrule(
            name = rule_name,
            srcs = [tmpl],
            outs = [outfile],
            cmd = _sed_cmd(subs),
            visibility = visibility,
        )
        out_files.append(":" + outfile)

    native.filegroup(
        name = name,
        srcs = out_files,
        visibility = visibility,
    )

def _sed_cmd(subs):
    # Literal substitution via sed; escape '&', '/', '\' for the replacement and
    # the delimiter. Keys are @TOKEN@ so they can't collide with LaTeX braces.
    parts = []
    for k, v in subs.items():
        esc = v.replace("\\", "\\\\").replace("&", "\\&").replace("|", "\\|")
        parts.append("-e 's|%s|%s|g'" % (k, esc))
    return "sed " + " ".join(parts) + " $< > $@"
