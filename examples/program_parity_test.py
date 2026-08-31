#!/usr/bin/env python3
"""One brand's mark, drawn twice, compared byte for byte.

THE CLAIM THIS TEST EXISTS TO MAKE HONEST. `MarkProgram` says a mark can be data
rather than code. That is easy to assert and easy to be wrong about: an
interpreter that produces a *plausible* mark — the same shapes, wound the other
way, or a circle where the generator hand-rolled a polygon — passes every visual
review and every screenshot, and fails the moment anyone diffs an artifact. So
the bar here is byte identity of every emitted SVG, not similarity.

That is a HIGHER bar than anything else in this repo, and worth saying so rather
than claiming precedent: `//marklib:gradient_parity_test` samples pixels with a
tolerance, because it compares two genuinely different renderers. This compares
two AUTHORS of the same renderer, so there is no tolerance to spend.

WHICH BRANDS, AND WHY THESE. leangres is the smoke test: four boxes and two
unions, enough to prove the Canvas seam and nothing more. citizen-sh is the gate.
Its colonnade is spaced by solving rather than tabulating — the file says so —
so reproducing it needs integer floor division, a conditional and an index, and
a transcription that hard-coded four x positions would pass a pixel comparison
while having thrown away the parametric mark. If this test ever covers only
leangres, it has stopped testing the thing it was written for.
"""
import json
import os
import sys
import unittest

# Every brand this test is supposed to cover. The env-var lookup below turns a
# missing entry into a failure rather than a silent skip, which is the same
# guard `//service:conformance_test` carries and for the same reason: a coverage
# gate that quietly checks less is worse than no gate.
BRAND = os.environ.get("BRAND", "")
# Both of these are RULE OUTPUTS: the brand's MarkProgram and its skin, each
# already converted from textproto to JSON by `//skins:skin_json`. Doing the
# conversion in the build rather than in the test is not just tidiness -- it
# means the stdlib parser that runs in a CONSUMER's build, where there is no
# protobuf wheel, has to swallow a whole MarkProgram before this test can even
# be built. A brand that cannot be parsed there cannot ship one, and this is
# where that is found out.
PROGRAM_JSON = os.environ.get("PROGRAM_JSON", "")
THEME_JSON = os.environ.get("THEME_JSON", "")


def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


class ProgramParityTest(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        for name, value in (("BRAND", BRAND),
                            ("PROGRAM_JSON", PROGRAM_JSON),
                            ("THEME_JSON", THEME_JSON)):
            self.assertTrue(value, "%s is unset; this target is misconfigured "
                                   "and would otherwise test nothing" % name)

    def _emit_both(self, tmp):
        import gen_mark

        from marklib import program

        native_dir = os.path.join(tmp, "generator")
        program_dir = os.path.join(tmp, "program")
        os.makedirs(native_dir)
        os.makedirs(program_dir)

        for variant in gen_mark.VARIANTS:
            gen_mark.canvas_for(variant).emit(
                os.path.join(native_dir, "%s_%s" % (BRAND, variant)))

        spec = _load(PROGRAM_JSON)
        theme = _load(THEME_JSON)
        program.emit(spec, program_dir, BRAND, program.variant_names(spec), theme=theme)
        return native_dir, program_dir

    def test_the_program_emits_the_same_files_as_the_generator(self):
        """The SET first, because a missing layer is not a byte difference.

        A transcription that dropped a layer would otherwise pass every
        comparison that ran.
        """
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            native_dir, program_dir = self._emit_both(tmp)
            self.assertEqual(sorted(os.listdir(native_dir)),
                             sorted(os.listdir(program_dir)))

    def test_every_emitted_file_is_byte_identical(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            native_dir, program_dir = self._emit_both(tmp)
            names = sorted(os.listdir(native_dir))
            self.assertTrue(names, "the generator emitted nothing")
            for name in names:
                with self.subTest(artifact=name):
                    with open(os.path.join(native_dir, name), "rb") as handle:
                        expected = handle.read()
                    with open(os.path.join(program_dir, name), "rb") as handle:
                        actual = handle.read()
                    self.assertEqual(
                        expected, actual,
                        "%s differs between %s/gen_mark.py and its MarkProgram"
                        % (name, BRAND))

    def test_the_program_states_no_colour_of_its_own(self):
        """Every colour resolves from the skin, not from a hex in the program.

        This is the half of the claim that byte identity does not check. A
        transcription that copied the generator's four hex constants would be
        byte-identical and would have recreated the duplication the format
        exists to remove -- and it would go on being byte-identical after the
        skin changed and the mark did not.

        A literal is legal in general: tomato's skin states that its mark's facet
        colours "are not palette roles", and that is a real decision. It is not
        this brand's, and a program that quietly acquired one should say so
        here first.
        """
        spec = _load(PROGRAM_JSON)
        literals = []

        def walk(node, path):
            if isinstance(node, dict):
                for key, value in node.items():
                    if key == "literal":
                        literals.append("%s = %s" % (path, value))
                    else:
                        walk(value, "%s.%s" % (path, key))
            elif isinstance(node, list):
                for i, value in enumerate(node):
                    walk(value, "%s[%d]" % (path, i))

        walk(spec, BRAND)
        self.assertEqual([], literals,
                         "these colours are stated in the program rather than "
                         "resolved from the skin: %s" % ", ".join(literals))


if __name__ == "__main__":
    sys.exit(not unittest.main(exit=False).result.wasSuccessful())
