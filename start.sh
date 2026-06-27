#!/usr/bin/env bash
# 一键起整个项目：后端 :8000 + 前端 :5173。Ctrl-C 一起退。
set -euo pipefail
cd "$(dirname "$0")"

# 依赖（幂等，已装则秒过）
(cd backend && uv sync -q)
(cd frontend && npm install --silent)

# 后端后台起，退出时一起收
(cd backend && uv run uvicorn app:app --port 8000) &
BACK=$!
trap 'kill $BACK 2>/dev/null' EXIT

echo
echo "  🔊 前端页面   http://localhost:5173"
echo "  ⚙️  后端 API   http://localhost:8000"
echo "  📖 API 文档   http://localhost:8000/docs"
echo "  (Ctrl-C 停止全部)"
echo

# 前端占前台；它退了脚本就退，trap 顺手关后端
cd frontend && npm run dev
