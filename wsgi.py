#!/usr/bin/env python3
"""The deployed entrypoint for brando's deterministic tier.

WHY A FILE AT THE REPO ROOT. Vercel's Python runtime finds its application by
looking for a top-level `app` in one of a fixed set of filenames. `service/`
already contains `server.py`, which is on that list and defines no `app` — so
pointing the runtime at that directory finds the wrong file and fails in a way
that reads as a broken deployment rather than a misconfigured one. This sits
where the runtime looks, and does nothing but hand over the real application.

It also fixes the one thing that differs between the two hosts. Under Bazel the
generated protobuf modules arrive through the runfiles tree; there is no Bazel
here, so the vendored copies in `gen/` go on the path first. `gen/` is generated
code checked in with a regenerate-and-diff gate, exactly as `studio/agent/lib/brando/gen`
is — the same argument in the other language.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "gen"))

from service.connect_app import app  # noqa: E402  (the path fixup must come first)

__all__ = ["app"]
