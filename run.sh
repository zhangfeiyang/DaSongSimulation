#!/usr/bin/env bash
# 启动大宋模拟器
set -e
cd "$(dirname "$0")/backend"

if [ ! -d ".venv" ]; then
  echo "首次运行：创建虚拟环境并安装依赖…"
  python3 -m venv .venv
  ./.venv/bin/pip install -q -r requirements.txt
fi

echo "大宋模拟器启动中： http://127.0.0.1:8000"
exec ./.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
