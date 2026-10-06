#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
preview_env="${XDG_DATA_HOME:-$HOME/.local/share}/compoundos-owner-preview/local.env"
export GIT_SHA="$(git rev-parse HEAD)" BUILD_TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
docker compose --env-file "$preview_env" -p compoundos-owner-preview -f compose.yaml -f docker-compose.owner-preview.yml down
# No -v: preserve Preview records; unrelated projects are never touched.
