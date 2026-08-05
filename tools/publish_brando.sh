#!/usr/bin/env bash
# Publish a `.brando` as a GitHub Release asset.
#
#   tools/publish_brando.sh \
#       bazel-bin/examples/leangres/leangres_package.brando \
#       bazel-bin/examples/leangres/leangres_publish.json \
#       mattmarshall/brando v0.4.0
#
# THE PLAN IS A BUILD ARTIFACT; THIS IS ONLY THE UPLOAD. Every field a consumer
# pins — the content-addressed filename, the URL, the SRI integrity — is computed
# hermetically by `brand_publish_plan` and checked by `//tools:publish_plan_test`.
# This script does not recompute any of them; it uploads the bytes under the name
# the plan chose. If it derived the hash itself, the pin a human pastes and the
# pin the publisher used could differ, and the only symptom would be a consumer's
# fetch failing with what looks like a corrupted download.
#
# WHY A RELEASE AND NOT A CDN BUCKET. An earlier version of this pushed to aion's
# S3 + CloudFront lane, reasoning that reusing infrastructure beats building it.
# That reasoning weighed whether the infrastructure existed and never weighed
# whose it was: brando and most of the brands it packages are personal projects,
# and a company's CDN is not the place for them. A release needs no
# infrastructure, lives on the repo that owns the brand, and is already how the
# Bazel registry serves module tarballs.
#
# IMMUTABILITY comes from the SRI pin, not from the host. A release asset CAN be
# replaced, unlike a content-addressed S3 key — but `rules_brand.from_url`
# requires `integrity`, so a swapped asset fails the consumer's fetch rather than
# restyling it. The hash in the filename keeps two builds from colliding; the
# integrity is what makes the URL mean one thing.
set -euo pipefail

pkg="${1:?the .brando to publish}"
plan="${2:?the publish plan JSON from brand_publish_plan}"
repo="${3:?owner/repo to publish the release on}"
tag="${4:?the release tag, e.g. v0.4.0}"

read -r key url integrity sha brand version < <(python3 -c '
import json, sys
p = json.load(open(sys.argv[1]))
print(p["key"], p["url"], p["integrity"], p["sha256"], p["brand"], p["version"] or "-")
' "$plan")

# The plan must describe THIS file. A stale plan beside a rebuilt package is the
# one way to publish bytes under a name that does not match them, which defeats
# content addressing silently -- the URL resolves, the integrity fails, and the
# error names a checksum rather than the mistake.
actual="$(shasum -a 256 "$pkg" | cut -d' ' -f1)"
if [[ "$actual" != "$sha" ]]; then
  echo "publish_brando: plan is stale — it describes $sha but $pkg is $actual" >&2
  echo "publish_brando: rebuild the publish plan target and retry" >&2
  exit 1
fi

# The plan's URL has to agree with where this is actually uploading, or the
# snippet a human pastes points somewhere the asset is not.
expected="https://github.com/${repo}/releases/download/${tag}/${key}"
if [[ "$url" != "$expected" ]]; then
  echo "publish_brando: the plan's URL does not match this release" >&2
  echo "  plan says: $url" >&2
  echo "  uploading: $expected" >&2
  echo "set base_url = https://github.com/${repo}/releases/download/${tag}" >&2
  exit 1
fi

if ! gh release view "$tag" --repo "$repo" >/dev/null 2>&1; then
  echo "publish_brando: release $tag does not exist on $repo" >&2
  echo "  gh release create $tag --repo $repo --title $tag --notes ..." >&2
  exit 1
fi

staged="$(mktemp -d)/${key}"
cp "$pkg" "$staged"

# --clobber, because the filename carries the content hash: re-uploading it means
# uploading identical bytes. A different build gets a different name.
gh release upload "$tag" "$staged" --repo "$repo" --clobber

cat <<EOF

publish_brando: ${brand} published to ${repo}@${tag}.

  url:       ${url}
  integrity: ${integrity}

Paste the generated snippet (<target>_publish_snippet.txt) into a consumer's
MODULE.bazel. The integrity is not optional and not decorative: a release asset
can be replaced, and the pin is what makes this URL mean one thing.
EOF
