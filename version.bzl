"""brando's version, in one place.

`MODULE.bazel` cannot `load()`, so a Bazel module has no way to hand its own
version to a BUILD file — which is why `brand_package`'s `brando_version` was a
hardcoded string that said `0.2.0` while `MODULE.bazel` said `0.3.0`. That field
is PROVENANCE: it is stamped into every `.brando` and is how a consumer answers
"which brando built this". A stale one is worse than an absent one.

The duplication is unavoidable; the drift is not. `//:version_test` reads both
and fails if they disagree.
"""

VERSION = "0.5.0"
