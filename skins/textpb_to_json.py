#!/usr/bin/env python3
"""Convert a meridian.theme.v1.Theme textproto to proto3-JSON (stdlib only).

The binary artifact (fastverk.binpb) is produced by `protoc --encode`, which
also VALIDATES the textproto against meridian's theme.proto at build time. This
tool produces the JSON twin the web binding consumes (`applyTheme(skin, mode)`)
from the SAME textproto, with no protobuf-runtime dependency (brand's pip lock
stays minimal).

It parses the small, fixed textproto grammar the Theme skin uses:
  * `key: "quoted string"`            (with \\" and \\\\ escapes)
  * `key: 123`                        (unquoted integer)
  * `name { ... }`                    (nested message; brace block)
  * `# comment` lines and blank lines.
Field names are kept snake_case to match theme/web/theme.ts's Theme interface;
uint32 fields are emitted as JSON numbers, everything else as strings.

CLI: textpb_to_json.py <skin.textpb> <skin.json>
"""
import json
import re
import sys

# uint32 fields in meridian.theme.v1 (Typography + Metrics) — emit as numbers.
_INT_FIELDS = {
    "base_size_px",
    "heading_weight",
    "body_weight",
    "radius_px",
    "unit_px",
}

# REPEATED fields in meridian.theme.v1. proto3-JSON represents a repeated field
# as an ARRAY — always, even at length 1 — and a decoder that expects an array
# rejects a bare object. The parser cannot infer arity from the textproto alone
# (`fonts { ... }` written once looks exactly like a singular message), so the
# repeated fields are named here, the same way _INT_FIELDS names the numerics.
#
# Getting this wrong is silent: before `fonts` every Theme field was singular,
# so repeated occurrences simply overwrote each other and a skin declaring three
# font sources emitted only the last one. The binpb was always correct — protoc
# handles repetition — so the two artifacts disagreed, and only the JSON twin,
# which is what the WEB consumes, lost data.
_REPEATED_FIELDS = {
    "fonts",
}

_TOKEN = re.compile(
    r"""
      (?P<comment>\#[^\n]*)               # comment to end of line
    | (?P<open>\{)                        # message open
    | (?P<close>\})                       # message close
    | (?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*:?  # field name (':' optional before '{')
    | (?P<string>"(?:\\.|[^"\\])*")       # quoted string
    | (?P<number>-?\d+)                   # integer
    | (?P<ws>\s+)                         # whitespace
    """,
    re.VERBOSE,
)


def _unescape(quoted: str) -> str:
    # Strip the surrounding quotes, then unescape \" and \\.
    inner = quoted[1:-1]
    return inner.replace('\\"', '"').replace("\\\\", "\\")


def _put(parent: dict, key: str, value: object) -> None:
    """Assign `key`, appending rather than overwriting for repeated fields."""
    if key in _REPEATED_FIELDS:
        parent.setdefault(key, []).append(value)
    elif key in parent:
        # A non-repeated field written twice is a schema slip, not something to
        # silently resolve by keeping whichever came last.
        raise ValueError(
            f"field {key!r} appears more than once but is not in _REPEATED_FIELDS; "
            f"add it there if the schema made it repeated"
        )
    else:
        parent[key] = value


def parse(text: str):
    """Parse the Theme textproto into a nested dict."""
    pos = 0
    pending_key = None
    stack = [{}]

    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m:
            raise ValueError(f"cannot tokenize at offset {pos}: {text[pos:pos+20]!r}")
        pos = m.end()
        kind = m.lastgroup
        if kind in ("comment", "ws"):
            continue
        if kind == "key":
            pending_key = m.group("key")
            continue
        if kind == "open":
            if pending_key is None:
                raise ValueError("'{' without a preceding field name")
            child: dict = {}
            _put(stack[-1], pending_key, child)
            stack.append(child)
            pending_key = None
            continue
        if kind == "close":
            stack.pop()
            if not stack:
                raise ValueError("unmatched '}'")
            continue
        if kind in ("string", "number"):
            if pending_key is None:
                raise ValueError("scalar without a preceding field name")
            if kind == "string":
                value: object = _unescape(m.group("string"))
            else:
                value = int(m.group("number"))
                if pending_key not in _INT_FIELDS:
                    # Defensive: a numeric on a non-int field is a schema slip.
                    raise ValueError(f"numeric value on string field {pending_key!r}")
            _put(stack[-1], pending_key, value)
            pending_key = None
            continue

    if len(stack) != 1:
        raise ValueError("unbalanced braces")
    return stack[0]


def main() -> None:
    src, dst = sys.argv[1], sys.argv[2]
    with open(src, "r", encoding="utf-8") as f:
        obj = parse(f.read())
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
