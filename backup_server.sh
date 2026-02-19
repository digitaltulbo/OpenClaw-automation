#!/bin/bash
# ═══════════════════════════════════════════
# Studio Bday - Server Backup & Migration Tool
# One-click backup from DigitalOcean to local
# ═══════════════════════════════════════════
set -e

REMOTE="root@104.248.144.183"
SSH_KEY="$HOME/.ssh/id_ed25519_agent"
SSH_OPTS="-o StrictHostKeyChecking=no -i $SSH_KEY"
BACKUP_DIR="$HOME/studio-server-backup"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="$BACKUP_DIR/$TIMESTAMP"

echo "═══════════════════════════════════════"
echo "📦 Studio Bday Server Backup"
echo "═══════════════════════════════════════"
echo "Target: $BACKUP_PATH"
echo ""

mkdir -p "$BACKUP_PATH"

# ── 1. Backup OpenClaw config & credentials ──
echo "📋 [1/5] OpenClaw 설정 & 인증정보 백업..."
ssh $SSH_OPTS $REMOTE "tar czf - -C /home/openclaw/.openclaw credentials workspace cron agents openclaw.json gateway-token.txt" \
  > "$BACKUP_PATH/openclaw-config.tar.gz"
echo "  ✅ openclaw-config.tar.gz"

# ── 2. Backup all custom scripts ──
echo "📋 [2/5] 자동화 스크립트 백업..."
ssh $SSH_OPTS $REMOTE "tar czf - -C /home/openclaw/.openclaw/skills seo-optimizer openclaw-auto-updater" \
  > "$BACKUP_PATH/skills.tar.gz"
echo "  ✅ skills.tar.gz"

# ── 3. Backup crontab ──
echo "📋 [3/5] Crontab 백업..."
ssh $SSH_OPTS $REMOTE "crontab -l -u openclaw 2>/dev/null || echo '# no crontab'" \
  > "$BACKUP_PATH/crontab.txt"
echo "  ✅ crontab.txt"

# ── 4. Backup rank history & logs ──
echo "📋 [4/5] 순위 히스토리 & 로그 백업..."
ssh $SSH_OPTS $REMOTE "cat /home/openclaw/.openclaw/skills/seo-optimizer/rank_history.json 2>/dev/null || echo '{}'" \
  > "$BACKUP_PATH/rank_history.json"
ssh $SSH_OPTS $REMOTE "cat /home/openclaw/.openclaw/logs/daily_report.log 2>/dev/null || echo 'no logs'" \
  > "$BACKUP_PATH/daily_report.log"
echo "  ✅ rank_history.json + logs"

# ── 5. Export OpenClaw cron jobs ──
echo "📋 [5/5] OpenClaw 크론 작업 내보내기..."
ssh $SSH_OPTS $REMOTE "sudo -u openclaw /usr/bin/node /opt/openclaw/dist/index.js cron list --json 2>/dev/null || echo '[]'" \
  > "$BACKUP_PATH/cron-jobs.json"
echo "  ✅ cron-jobs.json"

# ── Summary ──
echo ""
echo "═══════════════════════════════════════"
echo "✅ 백업 완료!"
echo "─────────────────────────────────────"
ls -lh "$BACKUP_PATH/"
echo ""
TOTAL=$(du -sh "$BACKUP_PATH" | cut -f1)
echo "📦 총 크기: $TOTAL"
echo "📍 위치: $BACKUP_PATH"
echo "═══════════════════════════════════════"
