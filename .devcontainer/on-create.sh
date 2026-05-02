#!/usr/bin/env bash
# Codespace prebuild 시점에 한 번 실행되는 스크립트.
# 무거운 의존성 설치는 모두 여기서 처리해 컨테이너 시작 시간을 줄인다.

set -e
echo "▶ [on-create] pip 업그레이드 및 의존성 설치 시작"

python -m pip install --upgrade pip wheel setuptools

# 본체 + GUI 의존성을 한 번에
pip install -r requirements.txt
pip install -r ui/requirements.txt

# editable install (소스 변경 즉시 반영)
pip install -e .

# 데이터 폴더 미리 생성 (런타임 IO 비용 절감)
mkdir -p data credentials

echo "✅ [on-create] 완료"
