#!/usr/bin/env bash
# 컨테이너가 시작될 때마다 실행.
# 1) .env 가 없으면 .env.example 을 복사 (자격증명/정책의 기본 템플릿 자동 제공)
# 2) Codespace Secret 으로 들어온 GOOGLE_APPLICATION_CREDENTIALS_JSON 을
#    실제 JSON 파일로 풀어서 GOOGLE_APPLICATION_CREDENTIALS 가 가리키게 한다.

set -e

# ── 1) .env 자동 복사 ─────────────────────────────────────
if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    cp .env.example .env
    echo "📝 [post-start] .env 가 없어 .env.example을 복사했습니다."
    echo "   필요하면 이 파일을 직접 수정하세요. (.gitignore에 막혀 커밋되지 않음)"
  fi
fi

# ── 2) GOOGLE_APPLICATION_CREDENTIALS_JSON Secret 펼치기 ─
if [ -n "${GOOGLE_APPLICATION_CREDENTIALS_JSON:-}" ]; then
  mkdir -p credentials
  CRED_PATH="credentials/service_account.json"
  printf '%s' "$GOOGLE_APPLICATION_CREDENTIALS_JSON" > "$CRED_PATH"
  chmod 600 "$CRED_PATH"
  # .env 에 경로 자동 반영
  if [ -f .env ]; then
    if grep -q "^GOOGLE_APPLICATION_CREDENTIALS=" .env; then
      sed -i.bak "s|^GOOGLE_APPLICATION_CREDENTIALS=.*|GOOGLE_APPLICATION_CREDENTIALS=$CRED_PATH|" .env
      rm -f .env.bak
    else
      echo "GOOGLE_APPLICATION_CREDENTIALS=$CRED_PATH" >> .env
    fi
  fi
  echo "🔐 [post-start] Codespace Secret 으로 자격증명 파일을 생성했습니다 ($CRED_PATH)"
fi

echo "✅ [post-start] 완료 — 'python main.py' 로 GUI를 시작하세요."
