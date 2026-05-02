#!/usr/bin/env bash
# Mac 더블클릭 실행 스크립트.
# Finder에서 이 파일을 한 번 더블클릭하면 UI가 브라우저로 자동으로 뜹니다.

set -e
cd "$(dirname "$0")/.."

# Python 자동 감지(python3 우선)
PY="$(command -v python3 || command -v python || true)"
if [[ -z "$PY" ]]; then
  echo "❌ Python을 찾지 못했습니다. https://www.python.org 에서 Python 3.10+ 를 설치해주세요."
  read -n 1 -s
  exit 1
fi

# 패키지 자동 설치 (최초 1회만 시간이 걸려요)
if ! "$PY" -c "import streamlit" >/dev/null 2>&1; then
  echo "▶ 첫 실행 — 필요한 패키지를 설치합니다 (1~2분)…"
  "$PY" -m pip install --upgrade pip
  "$PY" -m pip install -r ui/requirements.txt
fi

"$PY" main.py
