#!/usr/bin/env python3
"""Tests for marklib.program — the interpreter, in isolation.

Byte parity against the real generators lives in `//examples:*_program_parity`,
where the real generators are. This file covers what that cannot: the pieces no
example brand happens to use yet, and the failures a malformed program should
produce instead of a plausible mark.

The bias throughout is that a WRONG program must fail loudly. A mark that draws
is a mark someone ships; the expensive failures in this repo's history are all
the quiet ones — a layer written and silently dropped, a schema resolved by
accident, a gradient running the other way — so a program naming a shape that
does not exist should say which names do.
"""
import unittest

from marklib import program

THEME = {
    "light": {"bg": "#FFFFFF", "fg": "#111111", "accent": "#1B7A55"},
    "dark": {"bg": "#111111", "fg": "#EEEEEE", "accent": "#4FC08D"},
}


def _square(name="sq", x0="0", y0="0", x1="10", y1="10"):
    return {"name": name, "rect": {"x0": x0, "y0": y0, "x1": x1, "y1": y1}}


def _program(**overrides):
    base = {
        "canvas": 64,
        "params": [{"name": "size", "value": "10"}],
        "shapes": [_square()],
        "fit": {"bounds_of": "sq", "pad": "0.1"},
        "layers": [{"name": "body", "shape": "sq",
                    "fill": {"light": {"literal": "#123456"},
                             "dark": {"literal": "#654321"}}}],
        "variants": [{"name": "flat", "mode": "light"}],
    }
    base.update(overrides)
    return base


class ParameterTest(unittest.TestCase):
    def test_parameters_are_solved_in_order_and_see_their_predecessors(self):
        env = program.solve_params([
            {"name": "a", "value": "2"},
            {"name": "b", "value": "a * 3"},
        ], program._expr.Env())
        self.assertEqual(6.0, env.values["b"])

    def test_a_forward_reference_is_an_error(self):
        """Order is the feature, so reading ahead has to fail rather than
        silently produce whatever a later definition would have given."""
        with self.assertRaises(program._expr.ExprError):
            program.solve_params([{"name": "a", "value": "b + 1"},
                                  {"name": "b", "value": "1"}],
                                 program._expr.Env())

    def test_a_duplicate_parameter_is_an_error(self):
        with self.assertRaises(program.ProgramError):
            program.solve_params([{"name": "a", "value": "1"},
                                  {"name": "a", "value": "2"}],
                                 program._expr.Env())

    def test_list_and_table_parameters_survive(self):
        env = program.solve_params([
            {"name": "xs", "list": {"values": ["1", "2", "3"]}},
            {"name": "rows", "table": {"rows": [{"values": ["1", "2"]},
                                                {"values": ["3", "4"]}]}},
        ], program._expr.Env())
        self.assertEqual([1.0, 2.0, 3.0], env.values["xs"])
        self.assertEqual([[1.0, 2.0], [3.0, 4.0]], env.values["rows"])


class ShapeTest(unittest.TestCase):
    def _shapes(self, shapes, params=()):
        env = program.solve_params(list(params), program._expr.Env())
        return program.build_shapes({"shapes": shapes}, env)

    def test_an_unknown_shape_reference_lists_the_names_that_exist(self):
        with self.assertRaises(program.ProgramError) as caught:
            self._shapes([_square("a"),
                          {"name": "b", "union_of": {"shapes": ["a", "nope"]}}])
        self.assertIn("'nope'", str(caught.exception))
        self.assertIn("a", str(caught.exception))

    def test_a_shape_setting_two_forms_is_refused(self):
        with self.assertRaises(program.ProgramError):
            self._shapes([{"name": "x",
                           "rect": {"x0": "0", "y0": "0", "x1": "1", "y1": "1"},
                           "circle": {"cx": "0", "cy": "0", "r": "1"}}])

    def test_a_duplicate_shape_name_is_refused(self):
        with self.assertRaises(program.ProgramError):
            self._shapes([_square("a"), _square("a")])

    def test_difference_subtracts_every_named_shape(self):
        shapes = self._shapes([
            _square("outer", "0", "0", "10", "10"),
            _square("bite", "0", "0", "5", "10"),
            {"name": "rest", "difference_of": {"base": "outer", "subtract": ["bite"]}},
        ])
        self.assertAlmostEqual(50.0, shapes.get("rest").area)

    def test_repeat_binds_the_index_and_unions_by_default(self):
        shapes = self._shapes(
            [{"name": "bars", "repeat": {
                "count": "3", "index_var": "i",
                "body": {"rect": {"x0": "i * 10", "y0": "0",
                                  "x1": "i * 10 + 4", "y1": "1"}}}}])
        self.assertAlmostEqual(12.0, shapes.get("bars").area)

    def test_repeat_can_expose_its_instances_separately(self):
        """A fan whose blades alternate tone needs the pieces, not the union."""
        shapes = self._shapes(
            [{"name": "bars", "repeat": {
                "count": "2", "separate": True,
                "body": {"rect": {"x0": "i * 10", "y0": "0",
                                  "x1": "i * 10 + 4", "y1": "1"}}}}])
        self.assertAlmostEqual(4.0, shapes.get("bars.0").area)
        self.assertAlmostEqual(4.0, shapes.get("bars.1").area)

    def test_repeat_walks_a_table_row_by_row(self):
        """The values that genuinely are tabulated stay tabulated.

        brando's own four fingers each carry a knuckle, a reach and a curl. That
        is not a formula over an index, and a `repeat` that could only count
        would force those numbers back into code.
        """
        shapes = self._shapes(
            [{"name": "bars", "repeat": {
                "over": "rows",
                "body": {"rect": {"x0": "row[0]", "y0": "0",
                                  "x1": "row[0] + row[1]", "y1": "1"}}}}],
            params=[{"name": "rows", "table": {
                "rows": [{"values": ["0", "2"]}, {"values": ["10", "5"]}]}}])
        self.assertAlmostEqual(7.0, shapes.get("bars").area)

    def test_repeat_over_a_scalar_is_refused(self):
        with self.assertRaises(program.ProgramError):
            self._shapes([{"name": "bars", "repeat": {
                "over": "n", "body": {"rect": {"x0": "0", "y0": "0",
                                               "x1": "1", "y1": "1"}}}}],
                         params=[{"name": "n", "value": "3"}])

    def test_a_negative_buffer_erodes(self):
        """Negative distances are legal and load-bearing: brando's own palm is a
        positive buffer followed by a smaller negative one, and a hairline seam
        is closed by a matched pair."""
        shapes = self._shapes([
            _square("a", "0", "0", "10", "10"),
            {"name": "shrunk", "buffer": {"shape": "a", "distance": "-1"}},
        ])
        self.assertAlmostEqual(64.0, shapes.get("shrunk").area, places=6)

    def test_bbox_functions_read_shapes_declared_earlier(self):
        """tomato anchors its calyx off the body's own bounds. Without this a
        third of the corpus has to hand-transcribe a measurement, which is the
        drift the format exists to remove."""
        shapes = self._shapes([
            _square("body", "0", "0", "10", "20"),
            {"name": "anchor", "rect": {
                "x0": "bbox_cx(body)", "y0": "bbox_maxy(body)",
                "x1": "bbox_cx(body) + 1", "y1": "bbox_maxy(body) + 1"}},
        ])
        self.assertEqual((5.0, 20.0, 6.0, 21.0), shapes.get("anchor").bounds)

    def test_ngon_reproduces_the_hand_rolled_formula(self):
        """A shapely circle is not a hand-rolled n-gon, and substituting one for
        the other changes every coordinate in the emitted path."""
        shapes = self._shapes([{"name": "tri", "ngon": {
            "cx": "0", "cy": "0", "rx": "1", "sides": "3", "rot_deg": "90"}}])
        xs = sorted(round(x, 6) for x, _ in shapes.get("tri").exterior.coords[:-1])
        self.assertEqual(3, len(xs))
        self.assertAlmostEqual(0.0, xs[1])


class ColourTest(unittest.TestCase):
    def test_a_literal_is_returned_as_written(self):
        self.assertEqual("#ABCDEF", program.resolve_color(
            {"light": {"literal": "#ABCDEF"}}, "light", None, what="x"))

    def test_a_theme_reference_resolves_in_the_mode_it_names(self):
        """Not in the variant's mode. leangres draws its turnstile in the LIGHT
        palette's `bg` when it sits on ink, which is paper on ink -- a different
        statement from the dark palette's foreground."""
        self.assertEqual("#FFFFFF", program.resolve_color(
            {"dark": {"theme": {"mode": "light", "role": "bg"}}}, "dark", THEME, what="x"))

    def test_a_theme_reference_without_a_theme_says_so(self):
        with self.assertRaises(program.ProgramError) as caught:
            program.resolve_color({"light": {"theme": {"mode": "light", "role": "bg"}}},
                                  "light", None, what="layer 'body'")
        self.assertIn("no theme was supplied", str(caught.exception))

    def test_an_unknown_role_names_the_roles_that_exist(self):
        with self.assertRaises(program.ProgramError) as caught:
            program.resolve_color({"light": {"theme": {"mode": "light", "role": "primary"}}},
                                  "light", THEME, what="x")
        self.assertIn("accent", str(caught.exception))

    def test_a_role_the_brand_does_not_set_is_an_error_not_an_empty_fill(self):
        """An empty fill renders as black in some viewers and as nothing in
        others, and neither is the mark."""
        with self.assertRaises(program.ProgramError):
            program.resolve_color({"light": {"theme": {"mode": "light", "role": "muted"}}},
                                  "light", THEME, what="x")


class CanvasTest(unittest.TestCase):
    def test_a_variant_may_override_parameters(self):
        """brando's own variants differ by whether the bar carries a gradient. A
        variant that were only ever a mode and a ground could not reach that, and
        the brand would need a second program to say one different thing."""
        prog = _program(
            params=[{"name": "w", "value": "10"}],
            shapes=[_square("sq", "0", "0", "w", "10")],
            variants=[{"name": "flat", "mode": "light"},
                      {"name": "wide", "mode": "light",
                       "param_overrides": [{"name": "w", "value": "20"}]}])
        self.assertAlmostEqual(100.0, program.canvas_for(prog, "flat").layers[0].geom.area)
        self.assertAlmostEqual(200.0, program.canvas_for(prog, "wide").layers[0].geom.area)

    def test_a_variant_without_a_ground_is_transparent(self):
        canvas = program.canvas_for(_program(), "flat")
        self.assertIsNone(canvas.bg)

    def test_a_ground_becomes_the_background_layer(self):
        prog = _program(variants=[{"name": "flat", "mode": "light",
                                   "ground": {"light": {"literal": "#FFFFFF"}}}])
        canvas = program.canvas_for(prog, "flat")
        self.assertIsNotNone(canvas.bg)
        self.assertEqual("#FFFFFF", canvas.bg.fill)

    def test_composite_only_inverts_marklibs_emit_file(self):
        """proto3's false default has to be the ordinary case. brando's own mark
        has exactly one composite-only layer -- the halo separating the hand from
        the bar -- and it has no standalone asset by design."""
        prog = _program(layers=[
            {"name": "body", "shape": "sq", "fill": {"light": {"literal": "#111111"}}},
            {"name": "halo", "shape": "sq", "composite_only": True,
             "fill": {"light": {"literal": "#000000"}}},
        ])
        canvas = program.canvas_for(prog, "flat")
        self.assertEqual(["body"], [layer.name for layer in canvas.foreground_layers()])
        self.assertEqual(2, len(canvas.layers))

    def test_a_gradient_reaches_marklib_in_the_dict_form(self):
        prog = _program(layers=[{
            "name": "body", "shape": "sq",
            "fill": {"light": {"literal": "#111111"}},
            "gradient": {"angle_deg": "45", "stops": [
                {"color": {"light": {"literal": "#000000"}}},
                {"color": {"light": {"literal": "#FFFFFF"}}}]}}])
        gradient = program.canvas_for(prog, "flat").layers[0].gradient
        self.assertEqual(45.0, gradient["angle"])
        self.assertEqual(["#000000", "#FFFFFF"], gradient["stops"])

    def test_a_gradient_needs_two_stops(self):
        prog = _program(layers=[{
            "name": "body", "shape": "sq",
            "fill": {"light": {"literal": "#111111"}},
            "gradient": {"stops": [{"color": {"light": {"literal": "#000000"}}}]}}])
        with self.assertRaises(program.ProgramError):
            program.canvas_for(prog, "flat")

    def test_an_unknown_variant_lists_the_ones_this_program_has(self):
        with self.assertRaises(program.ProgramError) as caught:
            program.canvas_for(_program(), "inkbg")
        self.assertIn("flat", str(caught.exception))

    def test_fit_delegates_its_exactly_one_of_rule_to_marklib(self):
        """A second copy of that rule is a second place for it to be wrong."""
        prog = _program(fit={"bounds_of": "sq", "half_extent": "5"})
        with self.assertRaises(ValueError):
            program.canvas_for(prog, "flat")

    def test_camel_case_input_is_accepted(self):
        """A generated TypeScript client emits camelCase, and a mark that renders
        from Bazel but fails from the service would be miserable to debug."""
        prog = _program(layers=[{"name": "body", "shape": "sq",
                                 "compositeOnly": True,
                                 "fill": {"light": {"literal": "#111111"}}}])
        self.assertEqual([], program.canvas_for(prog, "flat").foreground_layers())


if __name__ == "__main__":
    unittest.main()
