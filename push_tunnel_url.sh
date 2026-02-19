#!/bin/bash
# 터널 URL을 추출하여 서버에 푸시
# LaunchAgent으로 터널 재시작 후 실행됨
TUNNEL_LOG="/tmp/studio-tunnel-error.log"
SSH_KEY="$HOME/.ssh/id_ed25519_agent"
REMOTE="root@104.248.144.183"
URL_FILE="/home/openclaw/.openclaw/dashboard_url.txt"

sleep 10  # 터널 시작 대기

URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | tail -1)

if [ -n "$URL" ]; then
    echo "$URL" | ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -i "$SSH_KEY" "$REMOTE" "cat > $URL_FILE" 2>/dev/null
    echo "$(date): Tunnel URL pushed: $URL" >> /tmp/studio-tunnel-url.log
fi
