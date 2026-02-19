# -*- coding: utf-8 -*-
"""
데이터 수집기 v1
- daily_report.py 실행 결과를 SQLite DB에 축적
- 예약 데이터, 순위, 키워드 통계 저장
- 대시보드 API에서 조회용
"""
import sqlite3, json, datetime, os, sys

DB_PATH = '/home/openclaw/.openclaw/skills/seo-optimizer/studio_data.db'

def get_db():
    """DB 연결, 테이블 자동 생성"""
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA journal_mode=WAL")
    
    # 예약 데이터
    db.execute("""CREATE TABLE IF NOT EXISTS reservations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        collected_at TEXT NOT NULL,
        studio TEXT NOT NULL,
        day_label TEXT,
        total_slots INTEGER DEFAULT 0,
        booked_slots INTEGER DEFAULT 0,
        available_slots INTEGER DEFAULT 0,
        rate REAL DEFAULT 0,
        booked_times TEXT,
        available_times TEXT,
        visitor_reviews INTEGER DEFAULT 0,
        blog_reviews INTEGER DEFAULT 0
    )""")
    
    # 키워드 순위
    db.execute("""CREATE TABLE IF NOT EXISTS rankings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        collected_at TEXT NOT NULL,
        keyword TEXT NOT NULL,
        our_rank INTEGER,
        competitors TEXT
    )""")
    
    # 키워드 검색량 (주간)
    db.execute("""CREATE TABLE IF NOT EXISTS keyword_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        keyword TEXT NOT NULL,
        pc_volume INTEGER DEFAULT 0,
        mobile_volume INTEGER DEFAULT 0,
        total_volume INTEGER DEFAULT 0,
        competition TEXT
    )""")
    
    db.commit()
    return db

def store_reservation(db, date_str, studio, day_data, reviews=None):
    """예약 데이터 저장"""
    booked_times = json.dumps([s["time"] for s in day_data.get("slots", []) if s.get("booked")], ensure_ascii=False)
    avail_times = json.dumps([s["time"] for s in day_data.get("slots", []) if not s.get("booked")], ensure_ascii=False)
    
    db.execute("""INSERT INTO reservations 
        (date, collected_at, studio, day_label, total_slots, booked_slots, available_slots, rate, booked_times, available_times, visitor_reviews, blog_reviews)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (date_str, datetime.datetime.now().isoformat(), studio, day_data.get("day_label", ""),
         day_data.get("total", 0), day_data.get("booked", 0), day_data.get("available", 0), day_data.get("rate", 0),
         booked_times, avail_times,
         reviews.get("visitor", 0) if reviews else 0, reviews.get("blog", 0) if reviews else 0))

def store_ranking(db, date_str, keyword, our_rank, competitors):
    """순위 데이터 저장"""
    db.execute("""INSERT INTO rankings (date, collected_at, keyword, our_rank, competitors)
        VALUES (?, ?, ?, ?, ?)""",
        (date_str, datetime.datetime.now().isoformat(), keyword, our_rank, json.dumps(competitors, ensure_ascii=False)))

def store_keyword_stats(db, date_str, stats_list):
    """검색량 데이터 저장"""
    for s in stats_list:
        if "error" in s:
            continue
        db.execute("""INSERT INTO keyword_stats (date, keyword, pc_volume, mobile_volume, total_volume, competition)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (date_str, s.get("keyword", ""), s.get("pc_volume", 0), s.get("mobile_volume", 0),
             s.get("total_volume", 0), s.get("competition", "")))

def collect_from_reservation_json(reservation_results):
    """reservation_estimator.py의 JSON 결과를 DB에 저장"""
    db = get_db()
    today = str(datetime.date.today())
    
    for result in reservation_results:
        studio = result.get("label", "")
        reviews = result.get("reviews", {})
        
        for day in result.get("days", []):
            store_reservation(db, today, studio, day, reviews)
    
    db.commit()
    db.close()

def collect_from_ranking_text(rank_text):
    """naver_rank_checker.py의 텍스트 결과를 파싱하여 DB에 저장"""
    import re
    db = get_db()
    today = str(datetime.date.today())
    
    current_keyword = None
    competitors = []
    our_rank = None
    
    for line in rank_text.split('\n'):
        kw_match = re.search(r"'(.+?)' 검색 결과", line)
        if kw_match:
            # 이전 키워드 저장
            if current_keyword:
                store_ranking(db, today, current_keyword, our_rank, competitors)
            current_keyword = kw_match.group(1)
            competitors = []
            our_rank = None
            continue
        
        rank_match = re.search(r'(\d+)위:\s*(.+?)(?:\s*👉|$)', line)
        if rank_match and current_keyword:
            rank_num = int(rank_match.group(1))
            name = rank_match.group(2).strip()
            competitors.append({"rank": rank_num, "name": name})
            if "👉" in line or "우리" in line:
                our_rank = rank_num
    
    # 마지막 키워드 저장
    if current_keyword:
        store_ranking(db, today, current_keyword, our_rank, competitors)
    
    db.commit()
    db.close()

def get_trends(days=30):
    """최근 N일간 예약 트렌드 조회 (대시보드용)"""
    db = get_db()
    cursor = db.execute("""
        SELECT date, studio, day_label, rate, booked_slots, total_slots, visitor_reviews
        FROM reservations
        WHERE date >= date('now', ?) 
        ORDER BY date, studio
    """, (f'-{days} days',))
    
    rows = cursor.fetchall()
    db.close()
    
    result = {}
    for row in rows:
        date, studio, label, rate, booked, total, reviews = row
        if date not in result:
            result[date] = {}
        if studio not in result[date]:
            result[date][studio] = []
        result[date][studio].append({
            "day_label": label, "rate": rate,
            "booked": booked, "total": total, "reviews": reviews
        })
    return result

def get_ranking_trends(days=30):
    """최근 N일간 순위 변동 조회"""
    db = get_db()
    cursor = db.execute("""
        SELECT date, keyword, our_rank
        FROM rankings
        WHERE date >= date('now', ?)
        ORDER BY date, keyword
    """, (f'-{days} days',))
    
    rows = cursor.fetchall()
    db.close()
    
    result = {}
    for date, keyword, rank in rows:
        if keyword not in result:
            result[keyword] = []
        result[keyword].append({"date": date, "rank": rank})
    return result

def get_summary():
    """전체 DB 요약"""
    db = get_db()
    stats = {}
    stats["total_reservations"] = db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
    stats["total_rankings"] = db.execute("SELECT COUNT(*) FROM rankings").fetchone()[0]
    stats["total_keywords"] = db.execute("SELECT COUNT(*) FROM keyword_stats").fetchone()[0]
    stats["date_range"] = {
        "from": db.execute("SELECT MIN(date) FROM reservations").fetchone()[0],
        "to": db.execute("SELECT MAX(date) FROM reservations").fetchone()[0],
    }
    db.close()
    return stats

if __name__ == "__main__":
    if "--summary" in sys.argv:
        print(json.dumps(get_summary(), ensure_ascii=False, indent=2))
    elif "--trends" in sys.argv:
        days = 30
        print("📊 예약 트렌드:")
        print(json.dumps(get_trends(days), ensure_ascii=False, indent=2))
    elif "--rankings" in sys.argv:
        print("🏆 순위 트렌드:")
        print(json.dumps(get_ranking_trends(), ensure_ascii=False, indent=2))
    else:
        print("Usage: data_collector.py [--summary|--trends|--rankings]")
        print("Programmatic: import and call collect_from_* functions")
