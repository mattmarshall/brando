"""`proto_descriptor_set`: emit a *self-contained* FileDescriptorSet.

The stock `proto_library` descriptor set holds only the DIRECT sources' file
descriptors — protoc reads transitive imports as side inputs but does not inline
them. So `protoc --encode --descriptor_set_in=<that>` fails with
"Could not find file in descriptor database", because the set it was handed does
not actually contain the schema it needs.

This runs protoc with `--include_imports` over the target's `ProtoInfo`, so the
result is complete and dependency-free: `brand_package` can encode a manifest
against brando.v1 with no `--proto_path` plumbing and no access to the .proto
sources in the consuming build.

Copied from meridian-k8s/tools/proto/defs.bzl, which savvifi-graph, governor and
jortz each also carry. Five copies of one 50-line rule is its own small argument
for a shared module, but that is not this change's fight.
"""

load("@rules_proto//proto:defs.bzl", "ProtoInfo")

def _proto_descriptor_set_impl(ctx):
    proto_info = ctx.attr.proto[ProtoInfo]
    out = ctx.actions.declare_file(ctx.label.name + ".binpb")

    args = ctx.actions.args()
    for p in proto_info.transitive_proto_path.to_list():
        args.add("--proto_path=" + p)
    args.add("--include_imports")
    args.add("--descriptor_set_out=" + out.path)
    for src in proto_info.direct_sources:
        args.add(src.path)

    ctx.actions.run(
        executable = ctx.executable._protoc,
        arguments = [args],
        inputs = proto_info.transitive_sources,
        outputs = [out],
        mnemonic = "ProtoDescriptorSet",
        progress_message = "Generating self-contained descriptor set %{label}",
    )
    return [DefaultInfo(files = depset([out]))]

proto_descriptor_set = rule(
    implementation = _proto_descriptor_set_impl,
    attrs = {
        "proto": attr.label(
            providers = [ProtoInfo],
            mandatory = True,
            doc = "proto_library target to encode (with all transitive imports inlined).",
        ),
        "_protoc": attr.label(
            default = "@protobuf//:protoc",
            executable = True,
            cfg = "exec",
        ),
    },
)
