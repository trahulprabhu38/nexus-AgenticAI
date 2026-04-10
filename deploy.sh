#!/usr/bin/env bash
# Build and push all Nexus agent images to Docker Hub.
# Usage:
#   ./deploy.sh              # builds + pushes multi-arch :latest (linux/amd64 + linux/arm64)
#   ./deploy.sh --no-push    # build only, no push (useful for local smoke test)
set -euo pipefail

REGISTRY="trahulprabhu38"
ROOT="$(cd "$(dirname "$0")" && pwd)"
PUSH=true
[[ "${1:-}" == "--no-push" ]] && PUSH=false

# Ensure a multi-platform builder exists
if ! docker buildx inspect nexus-builder &>/dev/null; then
  echo "==> Creating buildx builder 'nexus-builder'"
  docker buildx create --name nexus-builder --driver docker-container --use
else
  docker buildx use nexus-builder
fi
docker buildx inspect --bootstrap

# ── Services: folder | image-suffix ───────────────────────────────────────────
# image name = trahulprabhu38/nexus-<suffix>
# image tag  = :latest (multi-arch), :amd64, :arm64
declare -a SERVICES=(
  "Intent_Agent3        | intent_agent3"
  "table_agent          | table_agent"
  "column_pruning_agent | column_pruning_agent"
  "SQL_QUERY_GENERATOR  | sql_query_generator"
  "sql_validator_agent  | sql_validator_agent"
  "Audit_agent          | audit_agent"
  "synthetic-agent      | synthetic-agent"
  "retriever_agent      | retriever_agent"
  "frontend             | frontend"
  "db                   | db_init"
)

echo ""
echo "==> Building images (multi-arch: linux/amd64 + linux/arm64)"
echo ""

IMAGE_LIST=()

for entry in "${SERVICES[@]}"; do
  folder=$(echo "$entry" | awk -F'|' '{gsub(/ /,"",$1); print $1}')
  suffix=$(echo "$entry" | awk -F'|' '{gsub(/ /,"",$2); print $2}')
  # Docker requires lowercase image names
  suffix_lower=$(echo "$suffix" | tr '[:upper:]' '[:lower:]')
  IMAGE="${REGISTRY}/nexus-${suffix_lower}"
  CTX="${ROOT}/${folder}"

  echo "--- [${folder}] → ${IMAGE} ---"

  if [ "$PUSH" = true ]; then
    # Push multi-arch manifest as :latest (auto-selects correct arch on pull)
    docker buildx build \
      --platform linux/amd64,linux/arm64 \
      --push \
      -t "${IMAGE}:latest" \
      "${CTX}"

    # Also push platform-explicit tags for convenience
    docker buildx build \
      --platform linux/amd64 \
      --push \
      -t "${IMAGE}:amd64" \
      "${CTX}"

    docker buildx build \
      --platform linux/arm64 \
      --push \
      -t "${IMAGE}:arm64" \
      "${CTX}"
  else
    # Local load (single native arch, no push)
    docker buildx build \
      --load \
      -t "${IMAGE}:latest" \
      "${CTX}"
  fi

  IMAGE_LIST+=("${IMAGE}:latest  (multi-arch: amd64 + arm64)")
  IMAGE_LIST+=("${IMAGE}:amd64   (linux/amd64 — for EKS/K8s)")
  IMAGE_LIST+=("${IMAGE}:arm64   (linux/arm64 — for Mac testing)")
  echo ""
done

echo "==> All images built and pushed."
echo ""
echo "Docker Hub images:"
for img in "${IMAGE_LIST[@]}"; do
  echo "  $img"
done
