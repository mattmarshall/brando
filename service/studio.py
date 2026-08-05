#!/usr/bin/env python3
"""StudioService's engine — the model-assisted surface, and its safety rails.

FOUR PROPERTIES, EACH LEARNED SOMEWHERE ELSE IN THIS FLEET FIRST.

1. THE LOOP NEVER SEES SDK TYPES. `Engine` is three methods over plain dicts.
   `plugin-chat` arrived at the same shape, and the payoff is that swapping a
   backend is one class rather than a rewrite — and that the tests below need no
   AWS anything.

2. MOCK BY DEFAULT, selected by ENV. With `BRANDO_MODEL_ID` unset the engine is
   `MockEngine`, which is deterministic. Tests and CI therefore never reach
   Bedrock by accident, and neither does a developer who forgot to look. Making
   the safe path the default rather than the documented one is the difference
   between a rule and a hope.

3. EVERY ANSWER IS CACHED BY SPEC DIGEST. `plugin-builds` learned this
   expensively — an uncached model call on a read path re-bills on every viewer —
   and meridian-k8s caches enrichment by schema hash for the same reason. A
   critique of an unchanged brand IS the previous critique; recomputing it costs
   money to produce a different answer to the same question, which is worse than
   the cost.

4. EVERY PATH FAILS OPEN. A model error yields a deterministic result and a
   flag, never an exception. `plugin-builds` again: a brand pipeline that stops
   working because a model endpoint is down has taken a hard dependency it never
   needed. Copy is advisory; contrast is arithmetic and comes from marklib
   whatever the model does.

WHAT THE MODEL DOES NOT DO. It does not draw. `propose_spec` returns a BrandSpec
— numbers and hex codes — and the deterministic CSG pipeline executes them. A
mark a model drew pixel by pixel could not be re-rendered at another size, which
is the entire reason marklib exists.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Dict, List, Optional, Protocol

from service import render_core

# The model this service asks for when one is configured at all. An
# inference-profile id, matching how the fleet's other Bedrock callers address
# current Claude models — a bare foundation-model id is not routable for them.
DEFAULT_MODEL_ID = "us.anthropic.claude-opus-5"


def spec_digest(spec: dict) -> str:
    """A stable digest of a BrandSpec, for cache keys.

    Sorted and separator-normalised, so two dicts that differ only in key order
    or whitespace hash the same. They describe the same brand, and a cache that
    disagreed would re-bill for a formatting change.
    """
    canonical = json.dumps(spec, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class Engine(Protocol):
    """Three methods over plain dicts. No SDK types cross this line."""

    def propose_spec(self, brief: str, brand_id: str, constraints: dict) -> dict: ...
    def draft_copy(self, spec: dict, fields: List[str]) -> dict: ...
    def critique(self, spec: dict) -> List[dict]: ...


class MockEngine:
    """Deterministic answers, with no network.

    NOT a stub that returns empty. It produces a usable, obviously-neutral brand
    and critiques derived from what is actually absent from the spec, so a
    developer with no model configured still gets a working service and a
    reviewer can tell at a glance that no model was involved.
    """

    model_id = ""

    def propose_spec(self, brief: str, brand_id: str, constraints: dict) -> dict:
        # A greyscale palette with a single blue accent: legible, passes contrast,
        # and unmistakably a placeholder rather than a considered identity.
        spec = {
            "id": brand_id,
            "display_name": brand_id,
            "identity": {
                "positioning": brief.strip(),
                "story": "",
                "voice": ["Placeholder: no model was configured for this proposal."],
            },
        }
        theme = {
            "id": brand_id,
            "light": {
                "bg": "#FFFFFF", "surface": "#F4F4F5", "fg": "#18181B",
                "muted": "#52525B", "accent": "#1D4ED8", "accent_strong": "#1E3A8A",
                "on_accent": "#FFFFFF", "border": "#D4D4D8", "danger": "#B91C1C",
                "success": "#15803D", "warning": "#A16207", "info": "#1D4ED8",
                "code_fg": "#1E3A8A",
            },
            "dark": {
                "bg": "#18181B", "surface": "#27272A", "fg": "#FAFAFA",
                "muted": "#A1A1AA", "accent": "#93C5FD", "accent_strong": "#BFDBFE",
                "on_accent": "#10233F", "border": "#3F3F46", "danger": "#FCA5A5",
                "success": "#86EFAC", "warning": "#FCD34D", "info": "#93C5FD",
                "code_fg": "#BFDBFE",
            },
        }
        # A caller's constraints win over the placeholder: a rebrand usually is
        # not starting from nothing, and silently overriding a decided colour
        # would be the worst thing this method could do.
        if constraints.get("theme"):
            for mode in ("light", "dark"):
                theme.setdefault(mode, {}).update(constraints["theme"].get(mode, {}))
        spec["theme"] = theme
        return spec

    def draft_copy(self, spec: dict, fields: List[str]) -> dict:
        name = spec.get("display_name") or spec.get("id", "the brand")
        return {
            "positioning": spec.get("identity", {}).get("positioning", ""),
            "story": "",
            "voice": ["Placeholder copy for %s: no model was configured." % name],
        }

    def critique(self, spec: dict) -> List[dict]:
        """Findings from what is structurally ABSENT, which needs no model.

        This is the part worth having even when a model IS configured: "you did
        not write a story" is a fact, and asking a model to notice it wastes a
        call on something a dict lookup answers.
        """
        out = []
        identity = spec.get("identity", {})
        for field, why in (
            ("positioning", "A brand with no stated positioning cannot be critiqued "
                            "against its own claims."),
            ("story", "Without a story, every later copy decision is arbitrary."),
            ("voice", "Voice rules are what make copy reviewable by someone who "
                      "did not write it."),
        ):
            if not identity.get(field):
                out.append({
                    "subject": "identity.%s" % field,
                    "finding": "%s is empty." % field,
                    "suggestion": why,
                    "severity": "SEVERITY_NOTE",
                })
        if not spec.get("theme"):
            out.append({
                "subject": "theme",
                "finding": "The spec declares no Theme.",
                "suggestion": "Without one there is nothing to render and nothing "
                              "to check for contrast.",
                "severity": "SEVERITY_BLOCKING",
            })
        return out


class BedrockEngine:
    """The real backend. Imports the SDK lazily, so nothing here is needed to
    run, test or build the service without a model configured."""

    def __init__(self, model_id: str, region: str = "us-east-1"):
        self.model_id = model_id
        self._region = region
        self._client = None

    def _converse(self, system: str, user: str, schema: Optional[dict] = None) -> dict:
        # Imported HERE rather than at module scope: brando's pip lock should not
        # need boto3 for a build that never calls a model, and the mock path must
        # work in an environment that has no AWS anything.
        import boto3

        if self._client is None:
            self._client = boto3.client("bedrock-runtime", region_name=self._region)

        kwargs = {
            "modelId": self.model_id,
            "system": [{"text": system}],
            "messages": [{"role": "user", "content": [{"text": user}]}],
        }
        if schema is not None:
            # Structured output over the BrandSpec shape: the model picks the
            # numbers, and the deterministic pipeline executes them exactly.
            kwargs["toolConfig"] = {
                "tools": [{
                    "toolSpec": {
                        "name": "emit_brand_spec",
                        "description": "Return the proposed BrandSpec.",
                        "inputSchema": {"json": schema},
                    },
                }],
                "toolChoice": {"tool": {"name": "emit_brand_spec"}},
            }

        response = self._client.converse(**kwargs)
        for block in response["output"]["message"]["content"]:
            if "toolUse" in block:
                return block["toolUse"]["input"]
            if "text" in block:
                return {"text": block["text"]}
        return {}

    def propose_spec(self, brief: str, brand_id: str, constraints: dict) -> dict:
        result = self._converse(
            "You are a brand designer. Return a BrandSpec. Choose numbers and hex "
            "codes; you are not drawing anything.",
            "Brief: %s\nBrand id: %s\nAlready decided: %s"
            % (brief, brand_id, json.dumps(constraints)),
            schema={"type": "object"},
        )
        result.setdefault("id", brand_id)
        return result

    def draft_copy(self, spec: dict, fields: List[str]) -> dict:
        out = self._converse(
            "Write brand copy. Follow the brand's own voice rules if it has any.",
            "Spec: %s\nWrite: %s" % (json.dumps(spec), ", ".join(fields) or "all"),
        )
        return out if isinstance(out, dict) else {}

    def critique(self, spec: dict) -> List[dict]:
        out = self._converse(
            "Critique this brand. Say what contradicts what. Do not comment on "
            "colour contrast ratios; those are computed separately and precisely.",
            json.dumps(spec),
        )
        return out.get("critiques", []) if isinstance(out, dict) else []


def engine_from_env() -> Engine:
    """The engine this process should use.

    Unset `BRANDO_MODEL_ID` means MOCK, deliberately. The safe default is the
    one you get by doing nothing.
    """
    model_id = os.environ.get("BRANDO_MODEL_ID", "").strip()
    if not model_id:
        return MockEngine()
    return BedrockEngine(model_id, os.environ.get("AWS_REGION", "us-east-1"))


class Studio:
    """The service-facing surface: cached, and failing open."""

    def __init__(self, engine: Optional[Engine] = None):
        self._engine = engine or engine_from_env()
        self._fallback = MockEngine()
        self._cache: Dict[str, object] = {}

    @property
    def model_id(self) -> str:
        return getattr(self._engine, "model_id", "") or ""

    def _cached(self, kind: str, key: str, produce):
        """Returns (value, cached, model_id). Fails open to the mock."""
        cache_key = "%s:%s" % (kind, key)
        if cache_key in self._cache:
            return self._cache[cache_key], True, self.model_id
        try:
            value = produce(self._engine)
            model_id = self.model_id
        except Exception:
            # Deliberately broad. Any failure reaching a caller as an exception
            # would make a brand pipeline depend on a model endpoint being up,
            # which is the dependency this service must not create. The caller
            # learns a model was not involved from an EMPTY model_id, which is
            # the same signal the mock path gives.
            value = produce(self._fallback)
            model_id = ""
        self._cache[cache_key] = value
        return value, False, model_id

    def propose_spec(self, brief: str, brand_id: str, constraints: Optional[dict] = None):
        constraints = constraints or {}
        key = spec_digest({"b": brief, "i": brand_id, "c": constraints})
        spec, cached, model_id = self._cached(
            "propose", key, lambda e: e.propose_spec(brief, brand_id, constraints))
        # Contrast is COMPUTED, never asked for. A model can produce a plausible
        # palette that fails WCAG, and asking it to check its own arithmetic is
        # the wrong tool for the job.
        findings = render_core.contrast(spec.get("theme", {}))
        return {"spec": spec, "contrast": findings, "cached": cached, "model_id": model_id}

    def draft_copy(self, spec: dict, fields: Optional[List[str]] = None):
        fields = fields or []
        key = spec_digest({"s": spec, "f": sorted(fields)})
        identity, cached, model_id = self._cached(
            "copy", key, lambda e: e.draft_copy(spec, fields))
        return {"identity": identity, "cached": cached, "model_id": model_id}

    def critique(self, spec: dict):
        key = spec_digest(spec)
        critiques, cached, model_id = self._cached(
            "critique", key, lambda e: e.critique(spec))
        return {
            "critiques": critiques,
            # Kept SEPARATE from the model's critiques on purpose. Contrast is
            # arithmetic and is not negotiable; a model's opinion is. A reader
            # has to be able to tell which is which.
            "contrast": render_core.contrast(spec.get("theme", {})),
            "cached": cached,
            "model_id": model_id,
        }
