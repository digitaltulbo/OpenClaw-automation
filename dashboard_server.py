# -*- coding: utf-8 -*-
"""
Studio Bday 대시보드 서버 v1 (로컬용)
- FastAPI 기반 REST API + 정적 HTML 제공
- 예약 트렌드, 순위 변동, 인사이트 시각화
"""
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import sqlite3, json, os, sys, datetime

app = FastAPI(title="Studio Bday Dashboard", version="1.0")

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'studio_data.db')

def get_db():
    return sqlite3.connect(DB_PATH)

@app.get("/api/trends")
def api_trends(days: int = 30):
    db = get_db()
    cursor = db.execute("""
        SELECT date, studio, day_label, rate, booked_slots, total_slots, visitor_reviews
        FROM reservations WHERE date >= date('now', ?) ORDER BY date, studio
    """, (f'-{days} days',))
    rows = cursor.fetchall()
    db.close()
    result = {}
    for date, studio, label, rate, booked, total, reviews in rows:
        if date not in result: result[date] = {}
        if studio not in result[date]: result[date][studio] = []
        result[date][studio].append({"day_label": label, "rate": rate, "booked": booked, "total": total, "reviews": reviews})
    return result

@app.get("/api/rankings")
def api_rankings(days: int = 30):
    db = get_db()
    cursor = db.execute("""
        SELECT date, keyword, our_rank FROM rankings
        WHERE date >= date('now', ?) ORDER BY date, keyword
    """, (f'-{days} days',))
    rows = cursor.fetchall()
    db.close()
    result = {}
    for date, keyword, rank in rows:
        if keyword not in result: result[keyword] = []
        result[keyword].append({"date": date, "rank": rank})
    return result

@app.get("/api/summary")
def api_summary():
    db = get_db()
    stats = {
        "total_reservations": db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0],
        "total_rankings": db.execute("SELECT COUNT(*) FROM rankings").fetchone()[0],
        "total_keywords": db.execute("SELECT COUNT(*) FROM keyword_stats").fetchone()[0],
        "date_range": {
            "from": db.execute("SELECT MIN(date) FROM reservations").fetchone()[0],
            "to": db.execute("SELECT MAX(date) FROM reservations").fetchone()[0],
        }
    }
    db.close()
    return stats

@app.get("/api/insights")
def api_insights():
    db = get_db()
    insights = []
    # Recent reservation trends
    cursor = db.execute("""
        SELECT studio, AVG(rate) as avg_rate, MAX(rate) as max_rate, MIN(rate) as min_rate, COUNT(*) as cnt
        FROM reservations WHERE date >= date('now', '-7 days') AND rate > 0
        GROUP BY studio
    """)
    for studio, avg, mx, mn, cnt in cursor.fetchall():
        icon = "👉" if "스튜디오" in studio else "🎯"
        insights.append({
            "type": "reservation",
            "studio": studio,
            "message": f"{icon} {studio}: 최근 7일 예약률 평균 {avg:.0f}% (최고 {mx:.0f}%, 최저 {mn:.0f}%)",
            "value": round(avg, 1),
        })
    # Ranking changes
    cursor2 = db.execute("""
        SELECT keyword, our_rank, date FROM rankings ORDER BY date DESC LIMIT 20
    """)
    rows = cursor2.fetchall()
    kw_latest = {}
    for kw, rank, date in rows:
        if kw not in kw_latest:
            kw_latest[kw] = []
        kw_latest[kw].append(rank)
    for kw, ranks in kw_latest.items():
        if len(ranks) >= 2 and ranks[0] and ranks[1]:
            diff = ranks[1] - ranks[0]
            if diff != 0:
                direction = "🔼 상승" if diff > 0 else "🔽 하락"
                insights.append({"type": "ranking", "keyword": kw, "message": f"'{kw}' 순위 {direction} ({ranks[1]}위 → {ranks[0]}위)", "change": diff})
            else:
                insights.append({"type": "ranking", "keyword": kw, "message": f"'{kw}' 순위 유지 ({ranks[0]}위)", "change": 0})
    # Weekend analysis
    cursor3 = db.execute("""
        SELECT 
            CASE WHEN CAST(strftime('%w', date) AS INTEGER) IN (0, 6) THEN '주말' ELSE '평일' END as period,
            studio, AVG(rate) as avg_rate
        FROM reservations WHERE rate > 0 GROUP BY period, studio
    """)
    weekend_data = {}
    for period, studio, avg in cursor3.fetchall():
        if studio not in weekend_data: weekend_data[studio] = {}
        weekend_data[studio][period] = round(avg, 1)
    for studio, periods in weekend_data.items():
        if "주말" in periods and "평일" in periods:
            diff = periods["주말"] - periods["평일"]
            if diff > 5:
                insights.append({"type": "insight", "message": f"💡 {studio}: 주말 예약률이 평일보다 {diff:.0f}%p 높음 → 주말 타겟 프로모션 추천"})
    
    db.close()
    if not insights:
        insights.append({"type": "info", "message": "📊 데이터 축적 중. 2주 이후 의미 있는 인사이트 생성."})
    return insights

@app.get("/api/weekday-stats")
def api_weekday_stats():
    db = get_db()
    cursor = db.execute("""
        SELECT 
            CASE strftime('%w', date)
                WHEN '0' THEN '일' WHEN '1' THEN '월' WHEN '2' THEN '화'
                WHEN '3' THEN '수' WHEN '4' THEN '목' WHEN '5' THEN '금' WHEN '6' THEN '토'
            END as weekday,
            strftime('%w', date) as dow,
            studio, AVG(rate) as avg_rate, COUNT(*) as count
        FROM reservations WHERE rate > 0 GROUP BY dow, studio ORDER BY CAST(dow AS INTEGER)
    """)
    rows = cursor.fetchall()
    db.close()
    result = {}
    for weekday, _, studio, avg_rate, count in rows:
        if weekday not in result: result[weekday] = {}
        result[weekday][studio] = {"avg_rate": round(avg_rate, 1), "count": count}
    return result

@app.get("/", response_class=HTMLResponse)
def dashboard():
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.html")
    if os.path.exists(html_path):
        with open(html_path, 'r') as f:
            return f.read()
    return "<h1>dashboard.html not found</h1>"

if __name__ == "__main__":
    import uvicorn
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    print(f"🚀 Dashboard: http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
