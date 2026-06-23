#!/usr/bin/env bash
# docker-run.sh — build + chạy container 1 lượt, MOUNT bí mật từ host (không bake vào image).
# Yêu cầu: đã `fap login` TRÊN HOST trước (để output/token.json + oauth_tokens.json tồn tại),
# vì đăng nhập lần đầu cần trình duyệt; container chỉ `fap refresh` headless dùng lại.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

docker build -f deploy/Dockerfile -t fapc .
docker run --rm \
  -v "$REPO_ROOT/.env":/app/.env:ro \
  -v "$REPO_ROOT/credentials.json":/app/credentials.json:ro \
  -v "$REPO_ROOT/output":/app/output \
  fapc
