# -*- coding: utf-8 -*-
"""
Studio Bday - Integrated Morning Report v5
Report structure:
  매일 9시: 순위 + 예약현황
  매주 월요일: + 키워드 발굴 + 광고 키워드 분석  
"""
import subprocess, json, os, datetime, re, sys, requests

SCRIPTS_DIR = '/home/openclaw/.openclaw/skills/seo-optimizer/scripts'
HISTORY_FILE = '/home/openclaw/.openclaw/skills/seo-optimizer/rank_history.json'
NOTIFY_BOT_TOKEN = '8465933562:AAFhXEjUd8Hzw5HwqVpwlUltSz4WdzdBPXQ'
CHAT_ID = '1385089848'

def run_script(name, args=None, venv=False):
    python = '/home/openclaw/playwright-env/bin/python' if venv else 'python3'
    cmd = [python, os.path.join(SCRIPTS_DIR, name)]
    if args: cmd.extend(args)
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return res.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{NOTIFY_BOT_TOKEN}/sendMessage"
    # Telegram message limit is 4096 chars
    if len(msg) > 4000:
        msg = msg[:3990] + "\n...(일부 생략)"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg}, timeout=15)
        return True
    except: return False

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f: return json.load(f)
        except: pass
    return {"history": []}

def save_history(data):
    data['history'] = data['history'][-60:]
    with open(HISTORY_FILE, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def run_report():
    today = datetime.date.today()
    day_names = ['월', '화', '수', '목', '금', '토', '일']
    day_name = day_names[today.weekday()]
    is_monday = today.weekday() == 0
    force_weekly = "--force-weekly" in sys.argv
    
    msg = f"📊 [스튜디오생일] 오전 리포트\n"
    msg += f"📅 {today} ({day_name}요일)\n"
    msg += "═" * 28 + "\n"
    
    # ── 1. Daily: Competitive Rankings ──
    rank_output = run_script('naver_rank_checker.py')
    if rank_output:
        msg += f"\n{rank_output}"
    
    # Track history
    history = load_history()
    history['history'].append({"date": str(today), "raw": rank_output})
    save_history(history)
    
    # ── 2. Daily: Reservation Status (today + tomorrow) ──
    msg += f"\n\n{'─' * 28}\n"
    reservation_output = run_script('reservation_estimator.py', venv=True)
    if reservation_output:
        msg += f"\n{reservation_output}"
    else:
        msg += "\n📅 예약 현황: 데이터 로딩 실패"
    
    # ── 3. Weekly (Monday): Keyword Discovery + Ads Analysis ──
    if is_monday or force_weekly:
        msg += f"\n\n{'═' * 28}\n"
        msg += "📋 주간 리포트 (매주 월요일)\n"
        msg += "─" * 28 + "\n"
        
        # Keyword discovery
        kw_output = run_script('keyword_discovery.py')
        if kw_output:
            msg += f"\n{kw_output}"
        
        # Naver Ads keyword analysis
        msg += f"\n\n{'─' * 28}\n"
        ads_output = run_script('naver_ads_analyzer.py')
        if ads_output:
            msg += f"\n{ads_output}"
    
    msg += f"\n{'─' * 28}\n"
    if is_monday:
        msg += "✅ 일일+주간 통합 리포트 | 매일 오전 9시"
    else:
        msg += "✅ 일일 리포트 | 매일 오전 9시"
    
    success = send_telegram(msg)
    print(f"Report {'sent' if success else 'FAILED'} at {datetime.datetime.now()}")

if __name__ == "__main__":
    run_report()
