#!/usr/bin/env bash
set -e

# Unset any environment variables that conflict with nested npm runs
unset npm_config_allow_scripts

echo "=== Building SmiTriX Web App ==="
cd frontend
npm ci --ignore-scripts --legacy-peer-deps
VITE_DEMO=1 \
VITE_IMG_BASE="https://cdn.jsdelivr.net/gh/hasaneyldrm/exercises-dataset@7455efae41b330c265e7cd4b78dfa848e7ce5ebd/images/" \
VITE_GIF_BASE="https://cdn.jsdelivr.net/gh/hasaneyldrm/exercises-dataset@7455efae41b330c265e7cd4b78dfa848e7ce5ebd/videos/" \
npm run build

echo "=== App Build Complete in frontend/dist ==="
