#!/bin/bash
# AIdrama 启动脚本（macOS/Linux）
# 用法：chmod +x start.sh && ./start.sh

set -e

echo "==============================="
echo "  AIdrama 启动"
echo "==============================="

# 检查 Python
if ! command -v python3 &>/dev/null; then
  echo "❌ 未找到 python3，请先安装 Python 3.11+"
  exit 1
fi

# 检查 Node
if ! command -v node &>/dev/null; then
  echo "❌ 未找到 node，请先安装 Node.js 18+"
  exit 1
fi

# 检查 FFmpeg
if ! command -v ffmpeg &>/dev/null; then
  echo "⚠️  未找到 ffmpeg，合成整集功能将不可用"
  echo "   macOS 安装：brew install ffmpeg"
fi

# ── 后端 ──────────────────────────────────────────────
echo ""
echo "▶ 安装后端依赖..."
cd backend
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -r requirements.txt -q

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "⚠️  已生成 backend/.env，请填写 API Key 后重新启动"
fi

echo "▶ 启动 FastAPI 后端 (http://localhost:8000) ..."
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# ── 前端 ──────────────────────────────────────────────
cd ../frontend
echo ""
echo "▶ 安装前端依赖..."
npm install --silent

echo "▶ 启动 Next.js 前端 (http://localhost:3000) ..."
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ 启动完成！"
echo "   前端：http://localhost:3000"
echo "   后端：http://localhost:8000"
echo "   API文档：http://localhost:8000/docs"
echo ""
echo "按 Ctrl+C 停止所有服务"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo '已停止'" INT TERM
wait
