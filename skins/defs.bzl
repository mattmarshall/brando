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
contract is `@meridian//proto:theme.proto`; protoc comes from `@protobuf`.
"""

def brand_skin(name, textpb, visibility = None):
    """Compile a Theme textproto into <name>.binpb (validated) + <name>.json."""
    visibility = visibility or ["//visibility:public"]

    # binpb — `protoc --encode` over meridian's theme.proto (the validation gate).
    # theme.proto has no imports, so a single --proto_path suffices.
    native.genrule(
        name = "%s_binpb" % name,
        srcs = [
            textpb,
            "@meridian//proto:theme.proto",
        ],
        outs = ["%s.binpb" % name],
        cmd = (
            "$(execpath @protobuf//:protoc) " +
            "--encode=meridian.theme.v1.Theme " +
            "--proto_path=$$(dirname $(execpath @meridian//proto:theme.proto)) " +
            "$(execpath @meridian//proto:theme.proto) " +
            "< $(execpath %s) > $@" % textpb
        ),
        tools = ["@protobuf//:protoc"],
        visibility = visibility,
    )

    # textproto -> proto3-JSON (snake_case field names). Pure stdlib, so the
    # brand's pip lock needs no protobuf wheel; the binpb genrule is the gate.
    native.genrule(
        name = "%s_json" % name,
        srcs = [textpb],
        outs = ["%s.json" % name],
        cmd = "$(execpath @brando//skins:textpb_to_json) $(execpath %s) $@" % textpb,
        tools = ["@brando//skins:textpb_to_json"],
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
