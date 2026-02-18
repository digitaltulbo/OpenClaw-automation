#!/bin/bash
LOGFILE="/var/services/homes/jin/studio_automation/logs/scheduler.log"
SCRIPT="/var/services/homes/jin/studio_automation/scripts/auto_organizer_console.py"
PYTHON="/var/services/homes/jin/studio_automation/venv/bin/python"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] === 자동화 루프 시작 (5분 x 12회) ===" >> "$LOGFILE"

for i in $(seq 1 12); do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 실행 $i/12" >> "$LOGFILE"
    cd /var/services/homes/jin/studio_automation/scripts
    $PYTHON "$SCRIPT" >> "$LOGFILE" 2>&1
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 실행 $i/12 완료" >> "$LOGFILE"
    if [ $i -lt 12 ]; then
        sleep 300
    fi
done

echo "[$(date '+%Y-%m-%d %H:%M:%S')] === 자동화 루프 종료 ===" >> "$LOGFILE"
