"""brando brand_skin — the meridian-theme pipeline (textpb -> binpb -> json).

A brand authors its identity ONCE as a `meridian.theme.v1.Theme` textproto and
calls `brand_skin(name, textpb)`. This emits the two wire forms every meridian
renderer consumes:

  * `<name>_binpb` -> <name>.binpb : canonical binary Theme, via `protoc --encode`
    over meridian's theme.proto. This is ALSO the build-time validation gate —
    protoc rejects any field/type that doesn't match meridian.theme.v1.Theme, so
    the brand skin can't drift from the contract.
  * `<name>_json`  -> <name>.json  : the proto3-JSON twin for the web binding,
    produced by brando's stdlib textpb_to_json (no protobuf wheel needed).
  * `<name>`       -> filegroup of both, to stage next to a renderer.

meridian stays brand-neutral; the brand lives in the brand's repo. The schema
contract is `@meridian_schemas//proto:theme.proto`; protoc comes from `@protobuf`.

EVERY EXTERNAL LABEL BELOW IS A `Label()`, NOT A STRING, AND THAT IS LOAD-BEARING.
`brand_skin` is a legacy macro: it runs in the CALLER's package, and bzlmod
resolves a plain-string label with the CALLER's repo mapping. So a bare
"@meridian_schemas//proto:theme.proto" would mean whatever the consuming module
happens to map `meridian_schemas` to — or fail to resolve at all — and a consumer
with a differently-named alias would silently validate its skin against a
different schema. `Label()` is evaluated here, at load time, in brando's own
mapping, so every consumer gets exactly the schema brando pins in MODULE.bazel.

This bit for real: consumers previously validated against meridian 0.2.3's 69-line
theme.proto, which has no `Typography.display` (field 7) and no
`repeated FontSource fonts` (field 8) — so any skin declaring its own faces failed
the --encode gate, and aion forked these genrules to work around it.
"""

# Resolved in BRANDO's repo mapping (see the module docstring). Interpolating a
# Label into a cmd string yields its canonical form, which $(execpath) accepts.
_THEME_PROTO = Label("@meridian_schemas//proto:theme.proto")
_PROTOC = Label("@protobuf//:protoc")
_SKIN_JSON = Label("//skins:skin_json")
_THEME_SCHEMA = Label("//skins:theme_schema.json")
_THEME_MESSAGE = "meridian.theme.v1.Theme"

def brand_skin(name, textpb, visibility = None):
    """Compile a Theme textproto into <name>.binpb (validated) + <name>.json."""
    visibility = visibility or ["//visibility:public"]

    # binpb — `protoc --encode` over meridian's theme.proto (the validation gate).
    # theme.proto has no imports, so a single --proto_path suffices.
    native.genrule(
        name = "%s_binpb" % name,
        srcs = [
            textpb,
            _THEME_PROTO,
        ],
        outs = ["%s.binpb" % name],
        cmd = (
            "$(execpath %s) " % _PROTOC +
            "--encode=%s " % _THEME_MESSAGE +
            "--proto_path=$$(dirname $(execpath %s)) " % _THEME_PROTO +
            "$(execpath %s) " % _THEME_PROTO +
            "< $(execpath %s) > $@" % textpb
        ),
        tools = [_PROTOC],
        visibility = visibility,
    )

    # proto3-JSON (snake_case field names), driven by brando's committed
    # theme_schema.json — which is DERIVED from theme.proto by
    # //skins:regen_theme_schema and diffed by //skins:theme_schema_test, so the
    # arity/numeric facts are schema-derived rather than remembered.
    #
    # skin_json is STDLIB ONLY and must stay that way: it runs here, in the
    # CONSUMER's build, and a brand repo need not have rules_python at all
    # (savault and graph have no pip hub). A protobuf-wheel version was tried and
    # reverted — it failed a scratch consumer declaring only bazel_dep(brando)
    # with "No matching wheel for current configuration's Python version".
    native.genrule(
        name = "%s_json" % name,
        srcs = [
            textpb,
            _THEME_SCHEMA,
        ],
        outs = ["%s.json" % name],
        cmd = (
            "$(execpath %s) " % _SKIN_JSON +
            "--schema $(execpath %s) " % _THEME_SCHEMA +
            "--textpb $(execpath %s) " % textpb +
            "--out $@"
        ),
        tools = [_SKIN_JSON],
        visibility = visibility,
    )

    # Both artifacts together — stage this filegroup next to the renderer.
    native.filegroup(
        name = name,
        srcs = [
            ":%s_binpb" % name,
            ":%s_json" % name,
        ],
        visibility = visibility,
    )
