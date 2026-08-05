"""brando brand_package — build a `.brando` archive.

A `.brando` is one file a consumer can take instead of a pipeline: a zip holding
`brand.binpb` (a `brando.v1.BrandPackage`) and every artifact under a
content-addressed path. `rules_brand` unpacks it and exposes each logical name as
a target, so a repo that merely WEARS a brand needs no shapely, no Pillow, no pip
and no generators.

WHAT IT REPLACES. Two brands hand-assembled an asset zip — `aion-brand-assets.zip`
and `tbzl-brand-assets.zip` — with copy-pasted `pkg_files`/`pkg_zip` blocks, two
different directory layouts, two different naming conventions, and no manifest
inside either. Four of the six brands had no bundle at all. A zip with no manifest
is a bag of files: a consumer can extract it but cannot ask it for "the favicon"
without knowing what this particular brand called that.

THE MANIFEST IS PROTOC-VALIDATED, not merely produced. `pack_brand.py` is stdlib
and emits a textproto; `protoc --encode` turns it into the binary and rejects
anything that does not match `brando.v1`. That keeps the wheel out of a brand
repo's graph — the property `skin_json` had to be rebuilt to preserve — and makes
a malformed manifest a build failure rather than a runtime surprise.
"""

_PACK = Label("//tools:pack_brand")
_PROTOC = Label("@protobuf//:protoc")
_DESCRIPTOR_SET = Label("//proto/brando/v1:brand_descriptor_set")
_MESSAGE = "brando.v1.BrandPackage"
_PROTO_FILE = "brando/v1/brand.proto"

def _asset_arg(name, target, kind = None, variant = None, size_px = None, mode = None):
    """One `--asset` argument. Semicolon-separated because a logical name may
    contain a slash and a path may contain a comma."""
    parts = ["%s=$(execpath %s)" % (name, target)]
    if kind:
        parts.append("kind=%s" % kind)
    if variant:
        parts.append("variant=%s" % variant)
    if size_px != None:
        parts.append("size_px=%d" % size_px)
    if mode:
        parts.append("mode=%s" % mode)
    return ";".join(parts)

def brand_package(
        name,
        spec,
        assets,
        brando_version = "",
        source_repo = "",
        visibility = None):
    """Emit `<name>.brando` from a BrandSpec textproto and a set of artifacts.

    `assets` maps a LOGICAL NAME to either a label or a dict carrying the label
    plus optional `kind`/`variant`/`size_px`/`mode`. The logical name is what a
    consumer asks for and what `rules_brand` exposes as a target, so it is a
    stable API and should not encode a brand's internal filenames:

        assets = {
            "theme.json": "//skins:aion_json",
            "theme.binpb": "//skins:aion_binpb",
            "mark.svg": {"label": "//gen:aion_mark.svg", "kind": "ARTIFACT_KIND_MARK_SVG"},
            "icon-512.png": {
                "label": "//gen:aion_mark_512.png",
                "kind": "ARTIFACT_KIND_MARK_PNG",
                "size_px": 512,
            },
        }
    """
    visibility = visibility or ["//visibility:public"]

    labels = []
    asset_args = []
    for logical, value in assets.items():
        if type(value) == "string":
            label, meta = value, {}
        else:
            label, meta = value["label"], value
        labels.append(label)
        asset_args.append(_asset_arg(
            logical,
            label,
            kind = meta.get("kind"),
            variant = meta.get("variant"),
            size_px = meta.get("size_px"),
            mode = meta.get("mode"),
        ))

    args = " ".join(["--asset '%s'" % a for a in asset_args])

    # 1. Hash every asset and write the manifest as a textproto.
    native.genrule(
        name = "%s_manifest_textpb" % name,
        srcs = [spec] + labels,
        outs = ["%s_manifest.textpb" % name],
        cmd = (
            "$(execpath %s) manifest " % _PACK +
            "--spec $(execpath %s) " % spec +
            "--out $@ " +
            "--brando_version %s " % (brando_version or "unknown") +
            ("--source_repo %s " % source_repo if source_repo else "") +
            args
        ),
        tools = [_PACK],
        visibility = visibility,
    )

    # 2. Validate + encode. protoc is the gate: a manifest that does not match
    #    brando.v1 fails here rather than confusing a consumer later.
    native.genrule(
        name = "%s_manifest" % name,
        srcs = [
            "%s_manifest.textpb" % name,
            _DESCRIPTOR_SET,
        ],
        outs = ["%s_brand.binpb" % name],
        cmd = (
            "$(execpath %s) " % _PROTOC +
            "--encode=%s " % _MESSAGE +
            "--descriptor_set_in=$(execpath %s) " % _DESCRIPTOR_SET +
            # The trailing argument is the FILE, not the message — passing the
            # message name here yields "Could not find file in descriptor
            # database: brando.v1.BrandPackage".
            "%s " % _PROTO_FILE +
            "< $(execpath %s_manifest.textpb) > $@" % name
        ),
        tools = [_PROTOC],
        visibility = visibility,
    )

    # 3. Write the archive: the encoded manifest plus every blob, content-addressed.
    #    Deterministic (fixed mtimes, sorted entries) so two builds of the same
    #    brand produce identical bytes.
    native.genrule(
        name = name,
        srcs = ["%s_brand.binpb" % name] + labels,
        outs = ["%s.brando" % name],
        cmd = (
            "$(execpath %s) zip " % _PACK +
            "--manifest $(execpath %s_brand.binpb) " % name +
            "--out $@ " +
            args
        ),
        tools = [_PACK],
        visibility = visibility,
    )
