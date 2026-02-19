#!/bin/bash
# ═══════════════════════════════════════════
# Studio Bday - One-Click Local Deployment
# Deploys automation scripts on local Mac Mini
# GPU(OpenClaw) stays on cloud, scripts run locally
# ═══════════════════════════════════════════
set -e

BACKUP_DIR="${1:-$HOME/studio-server-backup/latest}"
INSTALL_DIR="$HOME/.studio-automation"

echo "═══════════════════════════════════════"
echo "🚀 Studio Bday Local Deployment"
echo "═══════════════════════════════════════"

# ── 1. Prerequisites ──
echo "📋 [1/6] 필수 의존성 확인..."
command -v python3 >/dev/null || { echo "❌ python3 not found"; exit 1; }
command -v pip3 >/dev/null || { echo "❌ pip3 not found"; exit 1; }
echo "  ✅ python3 & pip3 ready"

# ── 2. Create directory structure ──
echo "📋 [2/6] 디렉토리 생성..."
mkdir -p "$INSTALL_DIR/scripts"
mkdir -p "$INSTALL_DIR/credentials"
mkdir -p "$INSTALL_DIR/logs"
mkdir -p "$INSTALL_DIR/data"
echo "  ✅ $INSTALL_DIR"

# ── 3. Install Python dependencies ──
echo "📋 [3/6] Python 패키지 설치..."
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install playwright requests -q
echo "📋 [3b/6] Playwright Chromium 설치..."
"$INSTALL_DIR/venv/bin/python" -m playwright install chromium
echo "  ✅ Playwright + Chromium"

# ── 4. Restore from backup ──
echo "📋 [4/6] 백업에서 복원..."
if [ -f "$BACKUP_DIR/skills.tar.gz" ]; then
    tar xzf "$BACKUP_DIR/skills.tar.gz" -C "$INSTALL_DIR/" 2>/dev/null || true
    # Copy scripts to flat directory
    cp "$INSTALL_DIR/seo-optimizer/scripts/"*.py "$INSTALL_DIR/scripts/" 2>/dev/null || true
    echo "  ✅ 스크립트 복원"
fi
if [ -f "$BACKUP_DIR/openclaw-config.tar.gz" ]; then
    tar xzf "$BACKUP_DIR/openclaw-config.tar.gz" -C "$INSTALL_DIR/" 2>/dev/null || true
    cp "$INSTALL_DIR/credentials/"*.json "$INSTALL_DIR/credentials/" 2>/dev/null || true
    echo "  ✅ 인증정보 복원"
fi
if [ -f "$BACKUP_DIR/rank_history.json" ]; then
    cp "$BACKUP_DIR/rank_history.json" "$INSTALL_DIR/data/"
    echo "  ✅ 순위 히스토리 복원"
fi

# ── 5. Patch scripts for local paths ──
echo "📋 [5/6] 경로 패치..."
for f in "$INSTALL_DIR/scripts/"*.py; do
    if [ -f "$f" ]; then
        sed -i '' \
            -e "s|/home/openclaw/.openclaw/skills/seo-optimizer/scripts|$INSTALL_DIR/scripts|g" \
            -e "s|/home/openclaw/.openclaw/skills/seo-optimizer|$INSTALL_DIR/data|g" \
            -e "s|/home/openclaw/.openclaw/credentials|$INSTALL_DIR/credentials|g" \
            -e "s|/home/openclaw/.openclaw/logs|$INSTALL_DIR/logs|g" \
            -e "s|/home/openclaw/playwright-env/bin/python|$INSTALL_DIR/venv/bin/python|g" \
            "$f" 2>/dev/null || true
    fi
done
echo "  ✅ 로컬 경로로 변환 완료"

# ── 6. Register crontab ──
echo "📋 [6/6] Crontab 등록..."
PYTHON="$INSTALL_DIR/venv/bin/python"
CRON_LINE="0 9 * * * $PYTHON $INSTALL_DIR/scripts/daily_report.py >> $INSTALL_DIR/logs/daily_report.log 2>&1"

# Merge with existing crontab
(crontab -l 2>/dev/null | grep -v "daily_report.py"; echo "$CRON_LINE") | crontab -
echo "  ✅ 매일 오전 9시 리포트 등록"

# ── Test ──
echo ""
echo "═══════════════════════════════════════"
echo "✅ 로컬 배포 완료!"
echo "─────────────────────────────────────"
echo "📍 설치 위치: $INSTALL_DIR"
echo "🐍 Python: $PYTHON"
echo "📊 테스트: $PYTHON $INSTALL_DIR/scripts/daily_report.py"
echo "═══════════════════════════════════════"
