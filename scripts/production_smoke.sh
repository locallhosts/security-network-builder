#!/usr/bin/env bash
set -euo pipefail

: "${BASE_URL:?Set BASE_URL to the deployed service URL}"

echo "Health..."
curl --fail --silent --show-error "$BASE_URL/api/health" | grep -q 'security-network-builder'

echo "Readiness..."
curl --fail --silent --show-error "$BASE_URL/api/readiness"

echo "Versioned API..."
curl --fail --silent --show-error -D /tmp/snb-headers "$BASE_URL/api/v1/health" | grep -q 'security-network-builder'
grep -qi '^x-api-version: v1' /tmp/snb-headers

echo "Public search contract..."
curl --fail --silent --show-error "$BASE_URL/api/v1/search?q=security&limit=1" | grep -q 'results'

echo "Production smoke tests passed."