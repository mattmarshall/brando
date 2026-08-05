#!/usr/bin/env python3
"""Derive `theme_schema.json` from theme.proto. Runs in BRANDO ONLY.

WHY A COMMITTED ARTIFACT RATHER THAN A BUILD STEP.

The JSON twin of a skin has to know two things a textproto cannot tell you: which
fields are repeated (`fonts { ... }` written once looks exactly like a singular
message) and which are numeric. brando used to answer that with two hand-written
sets, which drifted and cost us the 0.1.1 repeated-field bug.

The obvious fix — decode the binpb with the protobuf runtime — was tried and
REVERTED, because it broke the contract that matters most about this tool: the
converter runs in the CONSUMER's build, and a brand repo need not have
`rules_python` at all. savault/brand and savvifi/graph/brand have no pip hub
whatsoever, and brando's `python.toolchain(is_default = True)` is root-module-only,
so a wheel dependency here fails their analysis outright with
`No matching wheel for current configuration's Python version`. The predecessor
said so in its own docstring — "pure stdlib, so the brand's pip lock needs no
protobuf wheel" — and that line was load-bearing.

So the schema is derived from the descriptor set HERE, in brando, where the
toolchain exists, and committed. `skin_json.py` stays stdlib and reads it.
`//skins:theme_schema_test` regenerates and diffs, so the file cannot go stale
without a red test: the tables are still schema-derived, just derived once.

CLI: regen_theme_schema.py --descriptor_set F --root M --out J
"""
from __future__ import annotations

import argparse
import json
import sys

from google.protobuf import descriptor, descriptor_pb2, descriptor_pool

# Field types that proto3-JSON renders as a NUMBER. The
# 64-bit types are deliberately absent: proto3-JSON encodes int64/uint64/fixed64
# as STRINGS, and emitting them as numbers would quietly lose precision above
# 2^53 for any future Theme field that uses one.
# Read straight off the FieldDescriptor, using the API upb actually exposes.
# Two things that look right and are not, both verified against protobuf 7.35.1:
# `field.CopyToProto(proto)` does not exist on `google._upb._message.
# FieldDescriptor`, and neither does `field.label` (deprecated in favour of
# `is_repeated`). upb is what ships in the wheel, so the pure-Python descriptor
# API is not available to fall back on.
_FD = descriptor.FieldDescriptor
_NUMERIC = {
    _FD.TYPE_DOUBLE, _FD.TYPE_FLOAT, _FD.TYPE_INT32, _FD.TYPE_FIXED32,
    _FD.TYPE_UINT32, _FD.TYPE_SFIXED32, _FD.TYPE_SINT32,
}
# 64-bit integers are the one type whose two encodings genuinely DISAGREE: a
# textproto writes `size_bytes: 4096` bare, but proto3-JSON writes "4096" as a
# STRING, because JSON numbers cannot hold the full int64 range without loss.
# They therefore need their own kind — classified as "number" the JSON is wrong,
# classified as "string" the parser rejects the unquoted textproto token.
_INT64 = {
    _FD.TYPE_INT64, _FD.TYPE_UINT64, _FD.TYPE_FIXED64,
    _FD.TYPE_SFIXED64, _FD.TYPE_SINT64,
}
_BOOL = _FD.TYPE_BOOL
_ENUM = _FD.TYPE_ENUM
_MESSAGE = _FD.TYPE_MESSAGE


def build(descriptor_set_path: str, root: str) -> dict:
    fds = descriptor_pb2.FileDescriptorSet()
    with open(descriptor_set_path, "rb") as fh:
        fds.ParseFromString(fh.read())
    pool = descriptor_pool.DescriptorPool()
    for file_proto in fds.file:
        pool.Add(file_proto)

    schema: dict = {}
    pending = [root]
    while pending:
        name = pending.pop()
        if name in schema:
            continue
        desc = pool.FindMessageTypeByName(name)
        fields = {}
        for field in desc.fields:
            entry = {"repeated": field.is_repeated}
            if field.type == _MESSAGE:
                entry["kind"] = "message"
                entry["type"] = field.message_type.full_name
                pending.append(field.message_type.full_name)
            elif field.type in _NUMERIC:
                entry["kind"] = "number"
            elif field.type in _INT64:
                entry["kind"] = "int64"
            elif field.type == _BOOL:
                entry["kind"] = "bool"
            elif field.type == _ENUM:
                # proto3-JSON writes an enum as its name string; a textproto
                # writes it as a BARE IDENTIFIER, which a tokenizer would
                # otherwise read as the next field name.
                entry["kind"] = "enum"
            else:
                entry["kind"] = "string"
            fields[field.name] = entry
        schema[name] = fields
    return {"root": root, "messages": schema}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--descriptor_set", required=True)
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(build(args.descriptor_set, args.root), fh, indent=2, sort_keys=True)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
