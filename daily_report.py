# -*- coding: utf-8 -*-
"""
Studio Bday - Integrated Morning Report v6
Report structure:
  매일 9시: 순위 + 예약현황 + DB저장
  매주 월요일: + 키워드 발굴 + 광고 분석 + 소식글 초안
"""
import subprocess, json, os, datetime, re, sys, requests

SCRIPTS_DIR = '/home/openclaw/.openclaw/skills/seo-optimizer/scripts'
HISTORY_FILE = '/home/openclaw/.openclaw/skills/seo-optimizer/rank_history.json'
NOTIFY_BOT_TOKEN = '8465933562:AAFhXEjUd8Hzw5HwqVpwlUltSz4WdzdBPXQ'
CHAT_ID = '1385089848'
DASHBOARD_URL_FILE = '/home/openclaw/.openclaw/dashboard_url.txt'

def get_dashboard_url():
    """대시보드 터널 URL 읽기"""
    try:
        with open(DASHBOARD_URL_FILE, 'r') as f:
            return f.read().strip()
    except:
        return None

def run_script(name, args=None, venv=False):
    python = '/home/openclaw/playwright-env/bin/python' if venv else 'python3'
    cmd = [python, os.path.join(SCRIPTS_DIR, name)]
    if args: cmd.extend(args)
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return res.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

def run_script_json(name, args=None, venv=False):
    """스크립트 실행 후 JSON 파싱"""
    raw = run_script(name, (args or []) + ['--json'], venv)
    try:
        return json.loads(raw)
    except:
        return None

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{NOTIFY_BOT_TOKEN}/sendMessage"
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

def store_to_db(rank_output, reservation_json, ads_json=None):
    """수집 데이터를 SQLite에 저장"""
    try:
        sys.path.insert(0, SCRIPTS_DIR)
        from data_collector import collect_from_ranking_text, collect_from_reservation_json, store_keyword_stats, get_db
        
        if rank_output:
            collect_from_ranking_text(rank_output)
        
        if reservation_json:
            collect_from_reservation_json(reservation_json)
        
        if ads_json:
            db = get_db()
            store_keyword_stats(db, str(datetime.date.today()), ads_json)
            db.commit()
            db.close()
        
        print("DB stored OK")
    except Exception as e:
        print(f"DB store error: {e}")

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
    
    # Track history (legacy JSON)
    history = load_history()
    history['history'].append({"date": str(today), "raw": rank_output})
    save_history(history)
    
    # ── 2. Daily: Reservation Status (today + tomorrow) ──
    msg += f"\n\n{'─' * 28}\n"
    reservation_output = run_script('reservation_estimator.py', venv=True)
    reservation_json = run_script_json('reservation_estimator.py', venv=True)
    if reservation_output:
        msg += f"\n{reservation_output}"
    else:
        msg += "\n📅 예약 현황: 데이터 로딩 실패"
    
    # ── 3. Weekly (Monday): Keyword Discovery + Ads + 소식글 ──
    ads_json = None
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
        ads_json = run_script_json('naver_ads_analyzer.py')
        if ads_output:
            msg += f"\n{ads_output}"
        
        # Place post draft (소식글 초안)
        msg += f"\n\n{'─' * 28}\n"
        post_output = run_script('place_post_generator.py')
        if post_output:
            msg += f"\n{post_output}"
    
    msg += f"\n{'─' * 28}\n"
    if is_monday or force_weekly:
        msg += "✅ 일일+주간 통합 리포트 | 매일 오전 9시"
    else:
        msg += "✅ 일일 리포트 | 매일 오전 9시"
    
    # Dashboard link
    dash_url = get_dashboard_url()
    if dash_url:
        msg += f"\n📊 대시보드: {dash_url}"
    
    # ── 4. Store to DB (silent) ──
    store_to_db(rank_output, reservation_json, ads_json)
    
    success = send_telegram(msg)
    print(f"Report {'sent' if success else 'FAILED'} at {datetime.datetime.now()}")

if __name__ == "__main__":
    run_report()
