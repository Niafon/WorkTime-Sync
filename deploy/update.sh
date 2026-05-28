#!/usr/bin/env bash
set -euo pipefail

cd /opt/WorkTime-Sync
git pull --ff-only

cd /opt/WorkTime-Sync-Front
git pull --ff-only

cd /opt/WorkTime-Sync
docker compose --env-file .env.production -f docker-compose.full.yml up -d --build
docker image prune -f
