#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
command -v docker >/dev/null
docker info >/dev/null
preview_config_dir="${XDG_DATA_HOME:-$HOME/.local/share}/compoundos-owner-preview"
mkdir -p "$preview_config_dir"; chmod 700 "$preview_config_dir"
preview_env="$preview_config_dir/local.env"
if [ ! -f "$preview_env" ]; then
  umask 077
  printf 'POSTGRES_PASSWORD=%s\nPOSTGRES_DB=compoundos_owner_preview_test\nENVIRONMENT=test\nCOMPOUNDOS_PUBLIC_ORIGIN=http://localhost:3802\n' "$(openssl rand -hex 24)" > "$preview_env"
fi
export GIT_SHA="$(git rev-parse HEAD)"
export BUILD_TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
preview_cached=""
if docker image inspect compoundos-v1-readiness-api:review >/dev/null 2>&1 && docker image inspect compoundos-v1-readiness-web:review >/dev/null 2>&1; then
  # Reuse only the reviewed RC dependency images, not arbitrary mutable tags.
  for preview_image in compoundos-v1-readiness-api:review compoundos-v1-readiness-web:review; do
    preview_revision="$(docker image inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$preview_image")"
    [ "$preview_revision" = "9ed4d55ea9e4ab8ee4a60bbcfbe38c3ba3ac409b" ] || { printf 'Unexpected cached RC image revision\n' >&2; exit 1; }
  done
  # Compile THIS worktree's frontend; bind its code to isolated runtime.
  command -v npm >/dev/null
  [ -d frontend/node_modules ] || (cd frontend && npm ci)
  COMPOUNDOS_PREVIEW_MODE=true NEXT_PUBLIC_COMPOUNDOS_PREVIEW_MODE=true API_INTERNAL_URL=http://api:8000 npm --prefix frontend run build
  preview_cached="-f docker-compose.owner-preview.cached.yml"
fi
preview_compose() { docker compose --env-file "$preview_env" -p compoundos-owner-preview -f compose.yaml -f docker-compose.owner-preview.yml $preview_cached "$@"; }
if [ -z "$preview_cached" ]; then preview_compose build api web migrate; fi
preview_compose up -d --wait postgres redis
preview_compose run --rm migrate
preview_compose run --rm --no-deps api python -m apps.api.services.preview_seed
preview_compose up -d --wait api web
printf '\nOwner Preview: http://localhost:3802\nAPI: http://localhost:8002/docs\nDEMO ONLY — local Owner access; no credentials required; no trades.\n'
