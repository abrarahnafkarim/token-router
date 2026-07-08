#!/usr/bin/env bash
# Build for linux/amd64 and push to a public registry.
# GHCR:      scripts/push_image.sh ghcr.io/YOUR_GH_USERNAME/token-router:latest
# DockerHub: scripts/push_image.sh YOUR_DH_USERNAME/token-router:latest
# GHCR login first:  echo "$GHCR_PAT" | docker login ghcr.io -u YOUR_GH_USERNAME --password-stdin
# Docker Hub login:  docker login -u YOUR_DH_USERNAME
# After a GHCR push: make the package PUBLIC in GitHub Packages settings,
# or the harness cannot pull it.
set -euo pipefail
cd "$(dirname "$0")/.."
REF="${1:?usage: push_image.sh <registry/name:tag>}"
docker buildx build --platform linux/amd64 -t "$REF" --push .
echo "pushed: $REF  (verify it is PUBLIC before submitting)"
