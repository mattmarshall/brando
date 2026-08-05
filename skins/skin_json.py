#!/usr/bin/env python3
"""Convert a meridian.theme.v1.Theme textproto to proto3-JSON. STDLIB ONLY.

Stdlib-only is a hard requirement, not a preference. This tool runs inside the
CONSUMER's build — every brand repo that calls `brand_skin` — and a brand repo
need not have `rules_python` at all: savault/brand and savvifi/graph/brand have no
pip hub whatsoever. brando's own `python.toolchain(is_default = True)` is
root-module-only, so any wheel dependency here fails those repos at analysis with
`No matching wheel for current configuration's Python version`. That was measured,
not assumed: a protobuf-runtime version of this file broke a scratch consumer that
declares nothing but `bazel_dep(brando)`.

WHAT IS DIFFERENT FROM THE VERSION THIS REPLACES.

The predecessor was also stdlib, and also parsed the textproto — but it carried
two HAND-WRITTEN sets, `_INT_FIELDS` and `_REPEATED_FIELDS`, because a tokenizer
cannot infer either from the text (`fonts { ... }` written once looks exactly like
a singular message). Those sets drifted, and the drift was silent: when `fonts`
became the first repeated field, occurrences overwrote each other and a skin
declaring three font sources emitted one. protoc handled the repetition correctly,
so the binpb was right and only the JSON — what the WEB reads — lost data.

Here the same facts come from `theme_schema.json`, which is DERIVED from
theme.proto by `regen_theme_schema.py` and checked by `//skins:theme_schema_test`.
So the tables are schema-derived rather than remembered, and this file has no
schema knowledge in it at all: adding a field to theme.proto needs no edit here.

CLI: skin_json.py --schema S --textpb T --out J
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any, Dict

_TOKEN = re.compile(
    r"""
      (?P<comment>\#[^\n]*)
    | (?P<open>\{)
    | (?P<close>\})
    | (?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*:?
    | (?P<string>"(?:\\.|[^"\\])*")
    | (?P<number>-?\d+(?:\.\d+)?)
    | (?P<ws>\s+)
    """,
    re.VERBOSE,
)

_BOOL = {"true": True, "false": False}


def _unescape(quoted: str) -> str:
    return quoted[1:-1].replace('\\"', '"').replace("\\\\", "\\")


class _Frame:
    __slots__ = ("obj", "type")

    def __init__(self, obj: dict, type_name: str):
        self.obj = obj
        self.type = type_name


def parse(text: str, schema: dict) -> dict:
    """Parse a Theme textproto into a proto3-JSON dict, driven by `schema`."""
    messages = schema["messages"]
    stack = [_Frame({}, schema["root"])]
    pending = None
    pos = 0

    def field(name: str) -> Dict[str, Any]:
        fields = messages.get(stack[-1].type, {})
        if name not in fields:
            raise ValueError(
                f"no field {name!r} in {stack[-1].type} — the skin does not match "
                f"the schema brando pins. Regenerate theme_schema.json if "
                f"theme.proto changed."
            )
        return fields[name]

    def put(name: str, value: Any) -> None:
        spec = field(name)
        target = stack[-1].obj
        if spec["repeated"]:
            target.setdefault(name, []).append(value)
        elif name in target:
            raise ValueError(f"field {name!r} is singular but appears more than once")
        else:
            target[name] = value

    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m:
            raise ValueError(f"cannot tokenize at offset {pos}: {text[pos:pos + 20]!r}")
        pos = m.end()
        kind = m.lastgroup
        if kind in ("comment", "ws"):
            continue
        if kind == "key":
            name = m.group("key")
            # A bare identifier is a VALUE when a field name is already pending:
            # `true`/`false` for a bool, and an enum constant for an enum. Both
            # lex identically to a field name, so only the schema can tell them
            # apart — which is the whole reason this reads one.
            if pending is not None and name in _BOOL and field(pending)["kind"] == "bool":
                put(pending, _BOOL[name])
                pending = None
            elif pending is not None and field(pending)["kind"] == "enum":
                put(pending, name)
                pending = None
            else:
                pending = name
            continue
        if kind == "open":
            if pending is None:
                raise ValueError("'{' without a preceding field name")
            spec = field(pending)
            if spec["kind"] != "message":
                raise ValueError(f"field {pending!r} is not a message but opens a block")
            child: dict = {}
            put(pending, child)
            stack.append(_Frame(child, spec["type"]))
            pending = None
            continue
        if kind == "close":
            stack.pop()
            if not stack:
                raise ValueError("unmatched '}'")
            continue
        if pending is None:
            raise ValueError("scalar without a preceding field name")
        spec = field(pending)
        if kind == "string":
            if spec["kind"] in ("number", "int64"):
                raise ValueError(f"field {pending!r} is numeric but got a quoted string")
            # Adjacent string literals CONCATENATE, as in C. This is how any
            # textproto wraps prose to a sane column width, and the parser this
            # replaced did not implement it either — nothing noticed, because no
            # skin had a field long enough to wrap. A BrandSpec does: `story` and
            # `description` are paragraphs. Without this, the second literal is a
            # scalar with no field name and the parse dies several lines later,
            # pointing at the wrong place.
            parts = [_unescape(m.group("string"))]
            while True:
                nxt = _TOKEN.match(text, pos)
                if not nxt:
                    break
                if nxt.lastgroup in ("comment", "ws"):
                    pos = nxt.end()
                    continue
                if nxt.lastgroup != "string":
                    break
                parts.append(_unescape(nxt.group("string")))
                pos = nxt.end()
            value: Any = "".join(parts)
        elif spec["kind"] == "int64":
            # Bare in the textproto, a STRING in proto3-JSON — JSON numbers
            # cannot carry the full int64 range without loss, so the wire format
            # quotes them. `size_bytes` is the first 64-bit field in the fleet.
            value = m.group("number")
        else:
            raw = m.group("number")
            if spec["kind"] != "number":
                # A number on a string field: proto3-JSON would emit it unquoted
                # and every consumer's type check would break.
                raise ValueError(f"field {pending!r} is a string but got a number")
            value = float(raw) if "." in raw else int(raw)
        put(pending, value)
        pending = None

    if len(stack) != 1:
        raise ValueError("unbalanced braces")
    return stack[0].obj


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--schema", required=True)
    ap.add_argument("--textpb", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    with open(args.schema, encoding="utf-8") as fh:
        schema = json.load(fh)
    with open(args.textpb, encoding="utf-8") as fh:
        obj = parse(fh.read(), schema)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2)
        fh.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
