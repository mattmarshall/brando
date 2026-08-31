#!/usr/bin/env python3
"""Tests for marklib.expr — the arithmetic, and the fence around it.

Two halves, and the second is the important one. The first checks that every
operator the corpus needs computes what it should. The second checks that
everything else is REFUSED, because this module's whole reason to exist is that
a MarkProgram may arrive from a model or off the wire and `eval` on either is
remote code execution. A parser that computes correctly and also reaches
`__import__` has failed at its actual job.
"""
import math
import unittest

from marklib import expr


def ev(text, **params):
    return expr.evaluate(text, expr.Env(params))


class ArithmeticTest(unittest.TestCase):
    def test_precedence_follows_mathematics(self):
        self.assertEqual(7.0, ev("1 + 2 * 3"))
        self.assertEqual(9.0, ev("(1 + 2) * 3"))
        self.assertEqual(-8.0, ev("-2 ^ 3"))
        # Right associative: 2^(3^2), not (2^3)^2.
        self.assertEqual(512.0, ev("2 ^ 3 ^ 2"))

    def test_the_operators_citizen_sh_needs(self):
        """The colonnade, in one expression each.

        `door = (gaps - 1) // 2` picks the middle intercolumniation, and the
        conditional widens only the gaps past it. Both were outside an earlier
        sketch of this grammar, and without them a transcription of citizen-sh
        has to hard-code four x positions -- at which point the mark has stopped
        being parametric, which is the whole thing the format is for.
        """
        self.assertEqual(1.0, ev("(gaps - 1) // 2", gaps=3))
        self.assertEqual(14.0, ev("i > door ? door_extra : 0", i=2, door=1, door_extra=14))
        self.assertEqual(0.0, ev("i > door ? door_extra : 0", i=0, door=1, door_extra=14))

    def test_floor_division_truncates_toward_negative_infinity(self):
        self.assertEqual(-2.0, ev("-3 // 2"))
        self.assertEqual(1.0, ev("3 // 2"))

    def test_modulo_of_a_negative_matches_fmod_not_python(self):
        """`-1 % 4` is 3 in Python and -1 in C, and geometry means the latter.

        tomato wraps an angle into (-pi, pi] with `(a + pi) % tau - pi`. Python's
        modulo would put a negative angle a full turn away from where the mark
        expects it, so this follows the sign of the left operand.
        """
        self.assertAlmostEqual(-1.0, ev("-1 % 4"))
        self.assertAlmostEqual(1.0, ev("1 % 4"))

    def test_comparison_and_boolean_operators_yield_numbers(self):
        self.assertEqual(1.0, ev("2 < 3"))
        self.assertEqual(0.0, ev("2 == 3"))
        self.assertEqual(1.0, ev("2 < 3 && 3 < 4"))
        self.assertEqual(1.0, ev("2 > 3 || 3 < 4"))

    def test_the_trigonometry_ngon_is_built_from(self):
        self.assertAlmostEqual(0.0, ev("sin(0)"))
        self.assertAlmostEqual(-1.0, ev("cos(pi)"))
        self.assertAlmostEqual(math.pi / 4, ev("atan2(1, 1)"))
        self.assertAlmostEqual(math.pi, ev("rad(180)"))

    def test_min_max_clamp_and_select(self):
        # brando's own corner clamp: `r = max(0, min(r, hw, hh))`.
        self.assertEqual(3.0, ev("max(0, min(r, hw, hh))", r=5, hw=3, hh=9))
        self.assertEqual(0.0, ev("max(0, min(r, hw, hh))", r=-5, hw=3, hh=9))
        self.assertEqual(7.0, ev("select(1, 7, 9)"))
        self.assertEqual(9.0, ev("select(0, 7, 9)"))
        self.assertEqual(5.0, ev("clamp(9, 1, 5)"))

    def test_parameters_may_be_lists_and_tables(self):
        """A scalar cannot hold `fingers`, and pretending otherwise loses tuning.

        brando's own mark carries four fingers, each with a knuckle, a reach and
        a curl -- hand-tuned values that are not a formula over an index and
        never will be.
        """
        env = expr.Env({"attach": [1.0, 2.0, 3.0],
                        "fingers": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]})
        self.assertEqual(2.0, expr.evaluate("attach[1]", env))
        self.assertEqual(0.6, expr.evaluate("fingers[1][2]", env))
        self.assertEqual(3.0, expr.evaluate("attach[-1]", env))

    def test_optional_reads_empty_as_the_documented_default(self):
        """proto3 cannot tell an unset string from an empty one, so "" must mean
        something, and every optional numeric field says what."""
        env = expr.Env()
        self.assertEqual(0.2, expr.evaluate_optional("", env, 0.2))
        self.assertEqual(0.2, expr.evaluate_optional(None, env, 0.2))
        self.assertEqual(1.0, expr.evaluate_optional("1", env, 0.2))


class RefusalTest(unittest.TestCase):
    """What the language will not do. This is the half that matters."""

    def test_python_is_not_reachable(self):
        for hostile in (
            "__import__('os').system('id')",
            "().__class__",
            "open('/etc/passwd')",
            "eval('1')",
            "exec('x=1')",
            "globals()",
            "lambda: 1",
        ):
            with self.subTest(source=hostile):
                with self.assertRaises(expr.ExprError):
                    ev(hostile)

    def test_an_unknown_name_is_an_error_not_a_zero(self):
        """Silently defaulting an unknown parameter to 0 would put a shape at the
        origin and look like a geometry bug for as long as anyone cared to
        look."""
        with self.assertRaises(expr.ExprError):
            ev("stem_x + 1")

    def test_an_unknown_function_is_refused_by_the_same_message_as_a_typo(self):
        with self.assertRaises(expr.ExprError):
            ev("system(1)")

    def test_attribute_access_does_not_parse(self):
        with self.assertRaises(expr.ExprError):
            ev("a.b", a=1)

    def test_division_by_zero_is_reported_not_raised_as_zerodivision(self):
        for source in ("1 / 0", "1 % 0", "1 // 0"):
            with self.subTest(source=source):
                with self.assertRaises(expr.ExprError):
                    ev(source)

    def test_an_out_of_range_index_names_the_length(self):
        env = expr.Env({"xs": [1.0, 2.0]})
        with self.assertRaises(expr.ExprError):
            expr.evaluate("xs[5]", env)

    def test_indexing_a_scalar_is_an_error(self):
        with self.assertRaises(expr.ExprError):
            ev("x[0]", x=1.0)

    def test_a_list_used_as_a_number_is_an_error(self):
        env = expr.Env({"xs": [1.0, 2.0]})
        with self.assertRaises(expr.ExprError):
            expr.evaluate("xs", env)

    def test_trailing_junk_is_refused(self):
        with self.assertRaises(expr.ExprError):
            ev("1 2")

    def test_unbalanced_parentheses_are_refused(self):
        with self.assertRaises(expr.ExprError):
            ev("(1 + 2")

    def test_bbox_needs_geometry_in_scope(self):
        """`bbox_minx(body)` is the one place a bare identifier is not evaluated.

        Without a shape resolver in the environment it must say so, rather than
        failing with a confusing message about an unknown name."""
        with self.assertRaises(expr.ExprError):
            ev("bbox_minx(body)")

    def test_bbox_reads_the_geometry_it_is_given(self):
        env = expr.Env({}, shape_bbox=lambda name: (1.0, 2.0, 5.0, 8.0))
        self.assertEqual(1.0, expr.evaluate("bbox_minx(body)", env))
        self.assertEqual(8.0, expr.evaluate("bbox_maxy(body)", env))
        self.assertEqual(4.0, expr.evaluate("bbox_width(body)", env))
        self.assertEqual(5.0, expr.evaluate("bbox_cy(body)", env))


class LexerTest(unittest.TestCase):
    def test_two_character_operators_win_over_one(self):
        """`<=` must not lex as `<` then `=`, and `//` must not lex as two `/`.

        Getting this ordering wrong produces a parser that computes something
        else without ever raising, which is the worst failure available here.
        """
        self.assertEqual(1.0, ev("2 <= 2"))
        self.assertEqual(1.0, ev("3 // 2"))
        self.assertEqual(1.5, ev("3 / 2"))

    def test_scientific_and_bare_decimal_notation(self):
        self.assertEqual(1500.0, ev("1.5e3"))
        self.assertEqual(0.5, ev(".5"))
        self.assertEqual(2.0, ev("2."))


if __name__ == "__main__":
    unittest.main()
