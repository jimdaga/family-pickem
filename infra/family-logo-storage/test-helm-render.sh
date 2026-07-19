#!/usr/bin/env bash
# Render-level assertions for the dedicated, ESO-managed logo storage secret.
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
chart="$repo_root/charts/family-pickem"

default_manifest=$(mktemp)
dev_manifest=$(mktemp)
prd_manifest=$(mktemp)
trap 'rm -f "$default_manifest" "$dev_manifest" "$prd_manifest"' EXIT

helm template family-pickem "$chart" >"$default_manifest"
helm template family-pickem-dev "$chart" -f "$repo_root/infra/app/values-dev.yaml" >"$dev_manifest"
helm template family-pickem-prd "$chart" -f "$repo_root/infra/app/values-prd.yaml" >"$prd_manifest"

! rg -F -- '-logo-storage' "$default_manifest"
rg -F 'family-pickem/dev/family-logo-storage' "$dev_manifest"
rg -F 'family-pickem/prd/family-logo-storage' "$prd_manifest"

# The name occurs once in the ExternalSecret target and once in each permitted
# Deployment container's envFrom block.
test "$(rg -c -- 'name: family-pickem-dev-logo-storage' "$dev_manifest")" -eq 3
test "$(rg -c -- 'name: family-pickem-prd-logo-storage' "$prd_manifest")" -eq 3

# No CronJob, including the backup job, may receive the dedicated credentials.
! rg -U -n 'kind: CronJob[\s\S]*?-logo-storage' "$dev_manifest" "$prd_manifest"
