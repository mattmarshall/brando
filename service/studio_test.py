"""Gate on StudioService's safety rails.

Each of these tests exists because the property it checks is invisible when it
breaks. A cache that stops caching still returns correct answers, and only the
bill changes. An engine that stops failing open works perfectly until the day the
endpoint is down. A default that flips from mock to live still passes every test
that has credentials.
"""

import os
import unittest

from service.studio import MockEngine, Studio, engine_from_env, spec_digest

SPEC = {
    "id": "t",
    "display_name": "T",
    "identity": {"positioning": "p", "story": "s", "voice": ["v"]},
    "theme": {
        "light": {"bg": "#FFFFFF", "fg": "#111111", "accent": "#1D4ED8",
                  "on_accent": "#FFFFFF", "muted": "#52525B"},
        "dark": {"bg": "#111111", "fg": "#FFFFFF", "accent": "#93C5FD",
                 "on_accent": "#10233F", "muted": "#A1A1AA"},
    },
}


class _Counting(MockEngine):
    """A mock that records how often it was actually reached."""

    def __init__(self):
        self.calls = 0

    def critique(self, spec):
        self.calls += 1
        return super().critique(spec)


class _Exploding(MockEngine):
    """Stands in for a model endpoint that is down."""

    model_id = "us.anthropic.claude-opus-5"

    def critique(self, spec):
        raise RuntimeError("bedrock unavailable")

    def propose_spec(self, brief, brand_id, constraints):
        raise RuntimeError("bedrock unavailable")


class Defaults(unittest.TestCase):
    def test_no_model_configured_means_mock(self):
        """The SAFE path is the one you get by doing nothing. If this ever
        inverts, CI starts billing and no test fails."""
        old = os.environ.pop("BRANDO_MODEL_ID", None)
        try:
            self.assertIsInstance(engine_from_env(), MockEngine)
        finally:
            if old is not None:
                os.environ["BRANDO_MODEL_ID"] = old

    def test_mock_reports_an_empty_model_id(self):
        """How a caller knows no model was involved. A mock claiming a model id
        would make a placeholder critique indistinguishable from a real one."""
        self.assertEqual("", Studio(MockEngine()).critique(SPEC)["model_id"])


class Caching(unittest.TestCase):
    def test_an_unchanged_spec_is_not_recomputed(self):
        engine = _Counting()
        studio = Studio(engine)
        studio.critique(SPEC)
        studio.critique(SPEC)
        self.assertEqual(1, engine.calls, "the second critique reached the engine")

    def test_the_second_answer_is_flagged_as_cached(self):
        studio = Studio(MockEngine())
        self.assertFalse(studio.critique(SPEC)["cached"])
        self.assertTrue(studio.critique(SPEC)["cached"])

    def test_a_changed_spec_is_recomputed(self):
        engine = _Counting()
        studio = Studio(engine)
        studio.critique(SPEC)
        studio.critique({**SPEC, "display_name": "different"})
        self.assertEqual(2, engine.calls)

    def test_key_order_and_whitespace_do_not_change_the_digest(self):
        """Two dicts describing the same brand must hash the same, or a
        formatting change re-bills."""
        self.assertEqual(
            spec_digest({"a": 1, "b": {"c": 2, "d": 3}}),
            spec_digest({"b": {"d": 3, "c": 2}, "a": 1}),
        )


class FailsOpen(unittest.TestCase):
    def test_an_engine_error_returns_a_result_rather_than_raising(self):
        """A brand pipeline must not stop working because a model endpoint is
        down. This is the dependency the service exists to avoid creating."""
        out = Studio(_Exploding()).critique(SPEC)
        self.assertIn("critiques", out)
        self.assertIsInstance(out["critiques"], list)

    def test_a_failed_call_reports_an_empty_model_id(self):
        """The caller has to be able to tell. A fallback that still claimed the
        model id would present placeholder text as a model's opinion."""
        self.assertEqual("", Studio(_Exploding()).critique(SPEC)["model_id"])

    def test_propose_still_returns_a_usable_spec_when_the_model_fails(self):
        out = Studio(_Exploding()).propose_spec("a brief", "newbrand")
        self.assertEqual("newbrand", out["spec"]["id"])
        self.assertIn("theme", out["spec"])


class ContrastIsComputed(unittest.TestCase):
    def test_contrast_accompanies_a_proposal(self):
        """A model can produce a plausible palette that fails WCAG. Asking it to
        check its own arithmetic is the wrong tool, so the numbers come from
        marklib whatever the model said."""
        out = Studio(MockEngine()).propose_spec("brief", "b")
        self.assertIn("contrast", out)
        self.assertIsInstance(out["contrast"], list)

    def test_critique_keeps_opinion_and_arithmetic_apart(self):
        """`critiques` is negotiable, `contrast` is not. A reader has to be able
        to tell which is which, so they are separate fields rather than one
        merged list."""
        out = Studio(MockEngine()).critique(SPEC)
        self.assertIn("critiques", out)
        self.assertIn("contrast", out)

    def test_the_mock_palette_is_actually_readable(self):
        """The placeholder has to pass the gate it ships beside. A default that
        failed contrast would teach every new brand to start from a broken
        palette."""
        out = Studio(MockEngine()).propose_spec("brief", "b")
        errors = [f for f in out["contrast"] if f["severity"] == "error"]
        self.assertEqual([], errors, "the placeholder palette is unreadable")


class MockCritique(unittest.TestCase):
    def test_it_finds_what_is_structurally_absent(self):
        """Worth having even with a model configured: "you did not write a
        story" is a dict lookup, not a question worth a model call."""
        findings = MockEngine().critique({"id": "x"})
        subjects = {f["subject"] for f in findings}
        self.assertIn("identity.story", subjects)
        self.assertIn("theme", subjects)

    def test_a_missing_theme_is_blocking(self):
        findings = MockEngine().critique({"id": "x"})
        theme = [f for f in findings if f["subject"] == "theme"][0]
        self.assertEqual("SEVERITY_BLOCKING", theme["severity"])

    def test_a_complete_spec_draws_no_structural_findings(self):
        self.assertEqual([], MockEngine().critique(SPEC))

    def test_caller_constraints_override_the_placeholder(self):
        """A rebrand is usually not starting from nothing, and silently
        overriding a decided colour is the worst thing propose_spec could do."""
        spec = MockEngine().propose_spec(
            "b", "x", {"theme": {"light": {"accent": "#7A2E52"}}})
        self.assertEqual("#7A2E52", spec["theme"]["light"]["accent"])


if __name__ == "__main__":
    unittest.main()
