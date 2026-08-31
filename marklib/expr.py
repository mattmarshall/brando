#!/usr/bin/env python3
"""brando marklib expr — the arithmetic a MarkProgram is allowed to do.

WHY A PARSER AND NOT `eval`. A MarkProgram may arrive from a model, from a
console, or over the wire, and `eval` on any of those is remote code execution
wearing a numeric costume. This module is a recursive-descent parser over a
closed grammar: numbers, named parameters, arithmetic, comparison, a conditional,
and a fixed function table. There is no attribute access, no call to anything not
in `_FUNCTIONS`, no assignment, and no way to name a Python object. What it
returns is a float.

WHY AN EXPRESSION LANGUAGE AT ALL, rather than numbers. Every generator in this
repo derives most of its measurements rather than stating them, and says so:
citizen-sh's colonnade spacing is "SOLVED rather than tabulated, so changing
`columns` or `door_extra` cannot leave the colonnade off-centre", and leangres
places both its bar and its halmos against a `mid` computed once from the stem.
A serialized dataclass of final coordinates would be a drawing; this is the
parametric mark those generators actually are.

THE GRAMMAR IS SIZED TO THE CORPUS, not guessed. Every operator here has a call
site in a real generator:

    //      citizen-sh's `door = (gaps - 1) // 2`, the middle intercolumniation
    ?:      the same file's `+ (door_extra if i == door else 0.0)`
    %       tomato's `i % 2` two-tone calyx, and its angle wrap
    sin/cos every `_ngon`, in three brands
    atan2   tomato's per-facet tone, taken from the facet midpoint's angle
    min/max brando's own `r = max(0, min(r, hw, hh))` corner clamp
    bbox_*  tomato's calyx anchor, measured off the body's own bounds

Anything NOT here was left out on purpose. There are no variables to assign, no
loops beyond `repeat`'s fixed count, and no recursion, so evaluation always
terminates -- which is the property that makes accepting one of these from a
stranger a bounded decision rather than a leap of faith.
"""
from __future__ import annotations

import math
import re
from typing import Callable, Dict, Optional, Sequence, Union

Number = float
# A parameter is a scalar, a list of scalars, or a table of rows. The list and
# table forms exist because the corpus genuinely has tables: brando's own mark
# carries `fingers` as four 3-tuples of hand-tuned values, which is not a formula
# over an index and never will be.
Value = Union[Number, list]


class ExprError(ValueError):
    """A malformed expression, or one that names something that does not exist.

    Its own class so a caller can tell "this program is wrong" from "this
    interpreter is broken", and report the former to whoever wrote the program.
    """


# ── tokens ────────────────────────────────────────────────────────────────────
# Longest-first, because `<=` must not lex as `<` then `=`, and `//` must not lex
# as two `/`. That ordering is the whole trick; getting it wrong produces a
# parser that silently computes something else.
_TOKEN = re.compile(
    r"""
    (?P<ws>\s+)
  | (?P<number>(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?)
  | (?P<name>[A-Za-z_]\w*)
  | (?P<op>//|<=|>=|==|!=|&&|\|\||[-+*/%^()\[\],?:<>])
    """,
    re.VERBOSE,
)


def _tokenize(text: str):
    out = []
    pos = 0
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if m is None:
            raise ExprError("unexpected character %r at %d in %r" % (text[pos], pos, text))
        pos = m.end()
        kind = m.lastgroup
        if kind == "ws":
            continue
        out.append((kind, m.group()))
    out.append(("end", ""))
    return out


# ── functions ─────────────────────────────────────────────────────────────────
def _select(cond, a, b):
    """`select(cond, a, b)` — the conditional as a call.

    `?:` reads better inline, but a three-argument form is what a program
    GENERATED rather than typed tends to produce, and supporting both costs one
    table entry.
    """
    return a if cond else b


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _sign(x):
    return 0.0 if x == 0 else math.copysign(1.0, x)


_FUNCTIONS: Dict[str, Callable[..., float]] = {
    "abs": abs,
    "min": min,
    "max": max,
    "floor": math.floor,
    "ceil": math.ceil,
    "round": lambda x, n=0: round(x, int(n)),
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "atan2": math.atan2,
    "hypot": math.hypot,
    "rad": math.radians,
    "deg": math.degrees,
    "sign": _sign,
    "clamp": _clamp,
    "select": _select,
}

_CONSTANTS = {"pi": math.pi, "tau": math.tau, "e": math.e}

# Functions whose single argument is a SHAPE NAME rather than a number. They are
# resolved by the interpreter, which is the only thing that knows what geometry
# exists; `expr` only knows they take a bare identifier and must not evaluate it.
BBOX_FUNCTIONS = ("bbox_minx", "bbox_miny", "bbox_maxx", "bbox_maxy",
                  "bbox_width", "bbox_height", "bbox_cx", "bbox_cy")


class Env:
    """Names an expression may read: parameters, loop bindings, and geometry.

    `shape_bbox` is supplied by the interpreter and is how an expression reaches
    a measurement it cannot compute — tomato anchors its calyx at
    `miny + calyx_y * body_h`, where `miny` comes from the body geometry's own
    bounds. Without it, a third of the corpus is inexpressible and the parameter
    would have to be hand-transcribed, which is the drift this whole format
    exists to remove.
    """

    __slots__ = ("values", "shape_bbox")

    def __init__(self, values: Optional[Dict[str, Value]] = None,
                 shape_bbox: Optional[Callable[[str], Sequence[float]]] = None):
        self.values: Dict[str, Value] = dict(values or {})
        self.shape_bbox = shape_bbox

    def child(self, **bindings: Value) -> "Env":
        """A scope with extra bindings — `repeat`'s `i`, `n` and `row`."""
        out = Env(self.values, self.shape_bbox)
        out.values.update(bindings)
        return out


class _Parser:
    """Recursive descent, lowest precedence first.

    Booleans are floats: comparisons yield 1.0 or 0.0, and anything non-zero is
    true. That keeps one value type in the language, which is what lets every
    field be `string` in the proto and every result be a coordinate.
    """

    def __init__(self, text: str, env: Env):
        self.text = text
        self.env = env
        self.tokens = _tokenize(text)
        self.i = 0

    # -- token helpers --
    def _peek(self):
        return self.tokens[self.i]

    def _next(self):
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def _accept(self, op: str) -> bool:
        kind, text = self._peek()
        if kind == "op" and text == op:
            self.i += 1
            return True
        return False

    def _expect(self, op: str):
        if not self._accept(op):
            kind, text = self._peek()
            raise ExprError("expected %r but found %r in %r" % (op, text or "end", self.text))

    # -- grammar --
    def parse(self) -> Value:
        value = self._ternary()
        kind, text = self._peek()
        if kind != "end":
            raise ExprError("trailing %r in %r" % (text, self.text))
        return value

    def _ternary(self):
        cond = self._or()
        if self._accept("?"):
            # Both arms are parsed whether or not they are taken. There are no
            # side effects and no division guard to protect, and parsing both
            # means a typo in the untaken arm is still an error rather than a
            # surprise the first time a parameter changes.
            a = self._ternary()
            self._expect(":")
            b = self._ternary()
            return a if cond else b
        return cond

    def _or(self):
        left = self._and()
        while self._accept("||"):
            right = self._and()
            left = 1.0 if (left or right) else 0.0
        return left

    def _and(self):
        left = self._comparison()
        while self._accept("&&"):
            right = self._comparison()
            left = 1.0 if (left and right) else 0.0
        return left

    _COMPARISONS = {
        "==": lambda a, b: a == b,
        "!=": lambda a, b: a != b,
        "<": lambda a, b: a < b,
        "<=": lambda a, b: a <= b,
        ">": lambda a, b: a > b,
        ">=": lambda a, b: a >= b,
    }

    def _comparison(self):
        left = self._additive()
        while True:
            kind, text = self._peek()
            if kind != "op" or text not in self._COMPARISONS:
                return left
            self.i += 1
            right = self._additive()
            left = 1.0 if self._COMPARISONS[text](left, right) else 0.0

    def _additive(self):
        left = self._multiplicative()
        while True:
            kind, text = self._peek()
            if kind != "op" or text not in ("+", "-"):
                return left
            self.i += 1
            right = self._multiplicative()
            left = left + right if text == "+" else left - right

    def _multiplicative(self):
        left = self._unary()
        while True:
            kind, text = self._peek()
            if kind != "op" or text not in ("*", "/", "%", "//"):
                return left
            self.i += 1
            right = self._unary()
            if text in ("/", "%", "//") and right == 0:
                raise ExprError("division by zero in %r" % self.text)
            if text == "*":
                left = left * right
            elif text == "/":
                left = left / right
            elif text == "%":
                left = math.fmod(left, right) if left * right < 0 else left % right
            else:
                left = float(math.floor(left / right))
        return left

    def _unary(self):
        if self._accept("-"):
            return -self._unary()
        if self._accept("+"):
            return self._unary()
        return self._power()

    def _power(self):
        base = self._postfix()
        if self._accept("^"):
            # Right associative, as in mathematics: 2^3^2 is 2^9.
            return base ** self._unary()
        return base

    def _postfix(self):
        value = self._atom()
        while self._accept("["):
            index = self._ternary()
            self._expect("]")
            value = _index(value, index, self.text)
        return value

    def _atom(self):
        kind, text = self._next()

        if kind == "number":
            return float(text)

        if kind == "op" and text == "(":
            value = self._ternary()
            self._expect(")")
            return value

        if kind == "name":
            if self._accept("("):
                return self._call(text)
            if text in _CONSTANTS:
                return _CONSTANTS[text]
            if text in self.env.values:
                return self.env.values[text]
            raise ExprError("unknown name %r in %r" % (text, self.text))

        raise ExprError("unexpected %r in %r" % (text or "end", self.text))

    def _call(self, name: str):
        if name in BBOX_FUNCTIONS:
            return self._bbox_call(name)

        fn = _FUNCTIONS.get(name)
        if fn is None:
            # Deliberately the same message whether the name is a typo or a real
            # Python builtin: `__import__` is not "not yet supported", it is not
            # a function of this language.
            raise ExprError("unknown function %r in %r" % (name, self.text))

        args = []
        if not self._accept(")"):
            args.append(self._ternary())
            while self._accept(","):
                args.append(self._ternary())
            self._expect(")")
        try:
            return float(fn(*args))
        except ExprError:
            raise
        except Exception as cause:
            raise ExprError("%s(%s) failed in %r: %s"
                            % (name, ", ".join("%g" % a for a in args), self.text, cause))

    def _bbox_call(self, name: str):
        """`bbox_minx(body)` — the one place a bare identifier is NOT evaluated.

        The argument names a shape, and a shape is not a number, so evaluating it
        would fail with a confusing message about an unknown name.
        """
        kind, shape = self._next()
        if kind != "name":
            raise ExprError("%s() takes a shape name, found %r in %r" % (name, shape, self.text))
        self._expect(")")
        if self.env.shape_bbox is None:
            raise ExprError("%s() is not available here (no geometry in scope)" % name)
        minx, miny, maxx, maxy = self.env.shape_bbox(shape)
        return {
            "bbox_minx": minx, "bbox_miny": miny,
            "bbox_maxx": maxx, "bbox_maxy": maxy,
            "bbox_width": maxx - minx, "bbox_height": maxy - miny,
            "bbox_cx": (minx + maxx) / 2.0, "bbox_cy": (miny + maxy) / 2.0,
        }[name]


def _index(value, index, text):
    if not isinstance(value, list):
        raise ExprError("cannot index a scalar in %r" % text)
    i = int(index)
    if i != index:
        raise ExprError("index %r is not an integer in %r" % (index, text))
    if not -len(value) <= i < len(value):
        raise ExprError("index %d out of range (%d entries) in %r" % (i, len(value), text))
    return value[i]


def evaluate(text: str, env: Env) -> float:
    """Evaluate `text` to a number.

    A list or table reaching here unindexed is an error rather than a silent
    coercion: `stem_x` where `fingers` was meant is a bug worth a message.
    """
    value = _Parser(str(text), env).parse()
    if isinstance(value, list):
        raise ExprError("%r is a list, not a number; index it" % text)
    return float(value)


def evaluate_optional(text: Optional[str], env: Env, default: float) -> float:
    """Evaluate `text`, or return `default` when it is empty.

    proto3 has no field presence for a scalar string, so "unset" and "" are the
    same thing on the wire. Every optional numeric field in a MarkProgram
    therefore means "empty is the documented default", and this is the one place
    that convention is implemented.
    """
    if text is None or str(text).strip() == "":
        return default
    return evaluate(text, env)
