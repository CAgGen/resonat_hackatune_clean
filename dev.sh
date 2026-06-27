#!/usr/bin/env bash
# 一键装环境。venv 由 uv 管：.venv 不存在就建、存在就复用，依赖按 uv.lock 同步（幂等）。
# 用法：./dev.sh            装后端依赖
#       ./dev.sh run        装好并起后端（:8000）
#       ./dev.sh front      装前端依赖并起前端（:5173）
set -euo pipefail
cd "$(dirname "$0")"

case "${1:-}" in
  front)
    cd frontend && npm install && npm run dev ;;
  run)
    cd backend && uv sync && uv run uvicorn app:app --reload --port 8000 ;;
  *)
    cd backend && uv sync
    echo "✅ 后端环境就绪 → backend/.venv"
    echo "   起后端: ./dev.sh run    起前端: ./dev.sh front"
    echo "   手动进 venv: source backend/.venv/bin/activate" ;;
esac
