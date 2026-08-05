#!/usr/bin/env python3
"""Generate Python gRPC stubs from the brando.v1 descriptor set.

WHY A SCRIPT RATHER THAN A RULE. rules_aip is a LINTING toolkit and says
multi-language stub generation is intentionally out of scope, so a caller has to
make the codegen choice explicitly. This is that choice: `grpc_tools.protoc`,
driven from the descriptor set the proto_library already produces.

Generating from the DESCRIPTOR SET rather than re-resolving .proto files matters:
the descriptor set is the artifact `aip_proto_lint` already checked and
`proto_descriptor_set` already closed over its imports, so the stubs cannot be
generated from a different view of the schema than the one that passed the gate.

CLI: gen_stubs.py --descriptor_set D --out_dir DIR --proto FILE...
"""
from __future__ import annotations

import argparse
import os
import sys


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--descriptor_set", required=True)
    ap.add_argument("--out_dir", required=True)
    ap.add_argument("--proto", action="append", required=True)
    args = ap.parse_args(argv)

    from grpc_tools import protoc

    os.makedirs(args.out_dir, exist_ok=True)
    argv_protoc = [
        "protoc",
        "--descriptor_set_in=%s" % args.descriptor_set,
        "--python_out=%s" % args.out_dir,
        "--grpc_python_out=%s" % args.out_dir,
    ] + args.proto

    rc = protoc.main(argv_protoc)
    if rc != 0:
        print("gen_stubs: protoc failed (%d)" % rc, file=sys.stderr)
    return rc


if __name__ == "__main__":
    sys.exit(main())
