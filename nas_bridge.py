#!/usr/bin/env python3
"""
NAS Bridge for Openclaw Studio Automation
Monitors the Studio NAS for new customer folders via SSH
and sends internal Telegram notifications via Openclaw.
"""

import subprocess
import time
import requests
import json
import os
import sys

# Configuration
NAS_USER = 'jin'
NAS_PASS = '1!Rlagmdrnr'
NAS_IP = '100.74.106.86'
NAS_PORT = '1222'
NAS_PATH = '/volume2/photo/BDAY-STUDIO/C/Original/원본사진'
CHECK_INTERVAL = 60  # seconds

OPENCLAW_URL = 'http://localhost:18789/api/v1/sessions/isolated/chat'
OPENCLAW_TOKEN = '43d214fef0affe746f05f3d1397382f7e8a0558a52ed3aa1c407fd0ec386f4aa'

DB_FILE = '/opt/studiobday-automation/seen_folders.json'


def get_nas_folders():
    """List folders on the NAS via SSH with sshpass and strict timeouts."""
    try:
        cmd = [
            'sshpass', '-p', NAS_PASS,
            'ssh',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'ConnectTimeout=10',
            '-o', 'ServerAliveInterval=5',
            '-o', 'ServerAliveCountMax=2',
            '-p', NAS_PORT,
            NAS_USER + '@' + NAS_IP,
            'ls -1 "' + NAS_PATH + '"'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        if result.returncode == 0:
            return set(line.strip() for line in result.stdout.splitlines() if line.strip())
        else:
            print(f'[WARN] NAS ls failed (rc={result.returncode}): {result.stderr.strip()}', flush=True)
            return set()
    except subprocess.TimeoutExpired:
        print('[WARN] SSH to NAS timed out after 20s', flush=True)
        return set()
    except Exception as e:
        print(f'[ERROR] NAS folder check: {e}', flush=True)
        return set()


def notify_openclaw(folder_name):
    """Send an internal notification via Openclaw Gateway."""
    print(f'[INFO] New folder detected: {folder_name}', flush=True)
    payload = {
        'message': '시스템 알림: NAS에 새로운 고객 촬영 폴더가 생성되었습니다: '
                   + folder_name + '. 관리를 시작해 주세요.',
        'stream': False
    }
    headers = {
        'Authorization': 'Bearer ' + OPENCLAW_TOKEN,
        'Content-Type': 'application/json'
    }
    try:
        response = requests.post(OPENCLAW_URL, json=payload, headers=headers, timeout=15)
        if response.status_code == 200:
            print('[INFO] Notification sent OK', flush=True)
        else:
            print(f'[WARN] Notification failed ({response.status_code}): {response.text[:200]}', flush=True)
    except Exception as e:
        print(f'[ERROR] Notification exception: {e}', flush=True)


def load_seen():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as f:
            try:
                return set(json.load(f))
            except Exception:
                return set()
    return None


def save_seen(seen):
    with open(DB_FILE, 'w') as f:
        json.dump(sorted(seen), f, ensure_ascii=False)


def main():
    print('[INFO] NAS Bridge starting...', flush=True)

    seen_folders = load_seen()
    if seen_folders is None:
        print('[INFO] First run — initializing folder snapshot...', flush=True)
        seen_folders = get_nas_folders()
        if seen_folders:
            save_seen(seen_folders)
            print(f'[INFO] Snapshot saved with {len(seen_folders)} folders.', flush=True)
        else:
            print('[WARN] Could not reach NAS on first run. Will retry.', flush=True)
            seen_folders = set()

    while True:
        current = get_nas_folders()
        if current:
            new = current - seen_folders
            for folder in sorted(new):
                notify_openclaw(folder)
                seen_folders.add(folder)
            if new:
                save_seen(seen_folders)
        time.sleep(CHECK_INTERVAL)


if __name__ == '__main__':
    main()
