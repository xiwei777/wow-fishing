#!/bin/bash
# 在 Mac 本机创建开发环境并打包 APP。
set -euo pipefail
cd "$(dirname "$0")/.."
if [ "$#" -ne 1 ]; then
  echo '用法: bash scripts/build_macos.command /路径/模型.pt'
  exit 1
fi
if [ ! -x .venv/bin/python ]; then
  python3.10 -m venv .venv
fi
.venv/bin/python -m pip install -r requirements-build.txt
.venv/bin/python scripts/build_app.py --model "$1"
