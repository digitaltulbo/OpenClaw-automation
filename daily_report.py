# -*- coding: utf-8 -*-
"""
Studio Bday - Integrated Morning Report v3.1
Includes detailed rankings and competitive insights.
"""
import subprocess
import json
import os
import datetime
import requests
import sys

SCRIPTS_DIR = '/home/openclaw/.openclaw/skills/seo-optimizer/scripts'
HISTORY_FILE = '/home/openclaw/.openclaw/skills/seo-optimizer/rank_history.json'
NOTIFY_BOT_TOKEN = '8465933562:AAFhXEjUd8Hzw5HwqVpwlUltSz4WdzdBPXQ'
CHAT_ID = '1385089848'

def run_script(script_name, args=None):
    cmd = ['python3', os.path.join(SCRIPTS_DIR, script_name)]
    if args:
        cmd.extend(args)
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        return res.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{NOTIFY_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg}
    try:
        resp = requests.post(url, json=payload, timeout=20)
        return resp.status_code == 200
    except:
        return False

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"history": []}

def save_history(data):
    data['history'] = data['history'][-60:] # Store 2 months
    with open(HISTORY_FILE, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def build_competitive_report():
    """Ranking report with history comparison"""
    output = run_script('naver_rank_checker.py')
    if not output:
        output = "❌ 순위 데이터를 가져오는 데 실패했습니다."
    
    history = load_history()
    today = str(datetime.date.today())
    
    # Simple change detection for the first keyword
    change_msg = ""
    target_pattern = r"(\d+)위: 스튜디오생일"
    current_match = re.search(target_pattern, output)
    
    if history['history']:
        last_raw = history['history'][-1].get('raw', '')
        last_match = re.search(target_pattern, last_raw)
        
        if current_match and last_match:
            curr_val = int(current_match.group(1))
            last_val = int(last_match.group(1))
            if curr_val < last_val:
                change_msg = f"\n📈 축하합니다! 검색 순위가 {last_val - curr_val}단계 상승했습니다!"
            elif curr_val > last_val:
                change_msg = f"\n📉 주의: 검색 순위가 {curr_val - last_val}단계 하락했습니다."
            else:
                change_msg = "\n✨ 순위가 어제와 동일하게 유지되고 있습니다."
    
    history['history'].append({"date": today, "raw": output})
    save_history(history)
    
    return output, change_msg

def build_keyword_report():
    today = datetime.date.today()
    # For testing, we can force it, but for production it's Monday
    if today.weekday() != 0 and "--force-keyword" not in sys.argv:
        return None
    
    output = run_script('keyword_discovery.py')
    return output if output else "❌ 키워드 발굴 데이터가 없습니다."

import re

def run_report():
    today = datetime.date.today()
    day_name = ['월', '화', '수', '목', '금', '토', '일'][today.weekday()]
    
    msg = f"📊 [스튜디오생일] 오전 리포트\n"
    msg += f"📅 {today} ({day_name}요일)\n"
    msg += f"{'═' * 28}\n\n"
    
    # 1. Competitive Rankings
    rank_output, change_msg = build_competitive_report()
    msg += rank_output
    if change_msg:
        msg += change_msg
    
    # 2. Keyword Discovery
    kw_report = build_keyword_report()
    if kw_report:
        msg += f"\n\n{'═' * 28}\n\n"
        msg += kw_report
    
    msg += f"\n\n{'─' * 28}\n"
    msg += "✅ 자동 생성 리포트 | 매일 오전 9시"
    
    # Send
    success = send_telegram(msg)
    print(f"Report {'sent' if success else 'FAILED'} at {datetime.datetime.now()}")

if __name__ == "__main__":
    run_report()
