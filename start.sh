#!/usr/bin/env bash
# One-shot start for the whole project: backend :8000 + frontend :5173. Ctrl-C stops both.
set -euo pipefail
cd "$(dirname "$0")"

# Dependencies (idempotent; already-installed deps finish quickly).
(cd backend && uv sync -q)
(cd frontend && npm install --silent)

# Start backend in the background and stop it on exit.
(cd backend && uv run uvicorn app:app --reload --port 8000) &
BACK=$!
trap 'kill $BACK 2>/dev/null' EXIT

echo
echo "  Frontend page   http://localhost:5173"
echo "  Backend API     http://localhost:8000"
echo "  API docs        http://localhost:8000/docs"
echo "  (Ctrl-C stops all)"
echo

# Frontend stays in the foreground; when it exits, the script exits and trap stops the backend.
cd frontend && npm run dev
