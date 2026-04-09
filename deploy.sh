#!/usr/bin/env bash
set -euo pipefail

REPO="trahulprabhu38"
TAG="${1:-linux}"
ROOT="$(cd "$(dirname "$0")" && pwd)"

# service_name | build_context | dockerfile_path | image_suffix
SERVICES=(
  "intent-agent     |.                  |Intent_Agent3/Dockerfile          |Intent_Agent3"
  "table-agent      |.                  |table_agent/Dockerfile            |table_agent"
  "column-pruning   |.                  |column_pruning_agent/Dockerfile   |column_pruning_agent"
  "sql-generator    |.                  |SQL_QUERY_GENERATOR/Dockerfile    |SQL_QUERY_GENERATOR"
  "sql-validator    |.                  |sql_validator_agent/Dockerfile    |sql_validator_agent"
  "audit-agent      |.                  |Audit_agent/Dockerfile            |Audit_agent"
  "orchestrator     |.                  |synthetic-agent/Dockerfile        |synthetic-agent"
  "frontend         |frontend           |Dockerfile                        |frontend"
)

#  "retriever-agent  |retriever_agent    |Dockerfile                        |retriever_agent"
echo "==> Building and pushing images (tag: $TAG)"
echo ""

for entry in "${SERVICES[@]}"; do
  # parse fields
  svc=$(echo "$entry"   | awk -F'|' '{gsub(/ /,"",$1); print $1}')
  ctx=$(echo "$entry"   | awk -F'|' '{gsub(/ /,"",$2); print $2}')
  dfile=$(echo "$entry" | awk -F'|' '{gsub(/ /,"",$3); print $3}')
  folder=$(echo "$entry"| awk -F'|' '{gsub(/ /,"",$4); print $4}')

  # lowercase folder name, replace underscores with hyphens for image name
  image_suffix=$(echo "$folder" | tr '[:upper:]' '[:lower:]' | tr '_' '-')
  IMAGE="${REPO}/nexus-${image_suffix}:${TAG}"

  echo "--- [$svc] ---"
  echo "    context   : $ctx"
  echo "    dockerfile: $dfile"
  echo "    image     : $IMAGE"

  docker build \
    --platform linux/amd64 \
    -f "${ROOT}/${dfile}" \
    -t "$IMAGE" \
    "${ROOT}/${ctx}"

  docker push "$IMAGE"
  echo ""
done

echo "==> All images built and pushed."
