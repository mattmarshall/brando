#!/usr/bin/env bash
# Publish a `.brando` to the aion static CDN, and update the package index.
#
#   AWS_PROFILE=aion-dev tools/publish_brando.sh \
#       bazel-bin/examples/leangres/leangres_package.brando \
#       bazel-bin/examples/leangres/leangres_publish.json
#
# THE PLAN IS A BUILD ARTIFACT; THIS IS ONLY THE UPLOAD. Every field a consumer
# pins — the content-addressed key, the URL, the SRI integrity — is computed
# hermetically by `brand_publish_plan` and checked by `//tools:publish_plan_test`.
# This script does not recompute any of them; it uploads the bytes to the key the
# plan names and records the pin. If it derived the hash itself, the pin a human
# pastes and the pin the publisher used could differ, and the only symptom would
# be a consumer's fetch failing with what looks like a corrupted download.
#
# Sits beside `aion/platform/tools/publish-brand.sh` and uses the same lane: the
# same private S3 bucket behind the same CloudFront OAC, the same immutable
# cache-control, and the same "no invalidation on publish" property, which holds
# because a key embeds its content hash and so never changes meaning. That script
# publishes loose assets under `brand/`; this publishes whole packages under
# `brando/`. Neither needs new infrastructure.
set -euo pipefail

pkg="${1:?the .brando to publish}"
plan="${2:?the publish plan JSON from brand_publish_plan}"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"
IMMUTABLE='public, max-age=31536000, immutable'

read -r key url integrity sha brand version < <(python3 -c '
import json, sys
p = json.load(open(sys.argv[1]))
print(p["key"], p["url"], p["integrity"], p["sha256"], p["brand"], p["version"] or "-")
' "$plan")

# The plan must describe THIS file. A stale plan beside a rebuilt package is the
# one way to publish bytes under a key that does not match them, which defeats
# content addressing silently -- the URL resolves, the integrity fails, and the
# error names a checksum rather than the mistake.
actual="$(shasum -a 256 "$pkg" | cut -d' ' -f1)"
if [[ "$actual" != "$sha" ]]; then
  echo "publish_brando: plan is stale — it describes $sha but $pkg is $actual" >&2
  echo "publish_brando: rebuild the publish plan target and retry" >&2
  exit 1
fi

bucket="$(aws cloudformation list-exports --region "$REGION" \
  --query "Exports[?Name=='AionStaticBucket'].Value" --output text)"
[[ -n "$bucket" && "$bucket" != "None" ]] || {
  echo "publish_brando: AionStaticBucket export not found — deploy aion-static first" >&2
  exit 1
}

prefix="${key%%/*}"

# Idempotent: a content-addressed key that already exists holds these exact
# bytes, so re-publishing is a no-op rather than a churn of the CDN.
if aws s3api head-object --bucket "$bucket" --key "$key" >/dev/null 2>&1; then
  echo "publish_brando: ${key} already published (content-addressed, so identical)"
else
  aws s3 cp "$pkg" "s3://${bucket}/${key}" \
    --content-type application/zip --cache-control "$IMMUTABLE" --only-show-errors
  echo "publish_brando: uploaded ${key}"
fi

# The mutable half: brand -> the current pin. Short TTL, because this is the one
# object whose meaning changes. A consumer reads it to FIND a version; it then
# pins the immutable URL, and never depends on this file again.
index="$(aws s3 cp "s3://${bucket}/${prefix}/packages.json" - 2>/dev/null || echo '{}')"
index="$(python3 -c '
import json, sys
idx = json.loads(sys.argv[1] or "{}")
idx[sys.argv[2]] = {
    "url": sys.argv[3],
    "integrity": sys.argv[4],
    "sha256": sys.argv[5],
    "brando_version": sys.argv[6],
}
print(json.dumps(idx, indent=2, sort_keys=True))
' "$index" "$brand" "$url" "$integrity" "$sha" "$version")"

echo "$index" | aws s3 cp - "s3://${bucket}/${prefix}/packages.json" \
  --content-type application/json --cache-control 'public, max-age=60' --only-show-errors

cat <<EOF

publish_brando: ${brand} published.

  url:       ${url}
  integrity: ${integrity}

Paste the generated snippet (<target>_publish_snippet.txt) into a consumer's
MODULE.bazel. The integrity is not optional and not decorative: without it a
swapped object at this URL restyles every consumer at once, silently.
EOF
