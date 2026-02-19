# -*- coding: utf-8 -*-
"""
Studio Bday 대시보드 서버 v1
- FastAPI 기반 REST API + 정적 HTML 제공
- 예약 트렌드, 순위 변동, 인사이트 시각화
"""
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import json, os, sys

# data_collector를 임포트
sys.path.insert(0, os.path.dirname(__file__))
from data_collector import get_trends, get_ranking_trends, get_summary, get_db

app = FastAPI(title="Studio Bday Dashboard", version="1.0")

# ══════════════════════════════════════
# API 엔드포인트
# ══════════════════════════════════════

@app.get("/api/trends")
def api_trends(days: int = 30):
    """최근 N일 예약률 트렌드"""
    return get_trends(days)

@app.get("/api/rankings")
def api_rankings(days: int = 30):
    """최근 N일 순위 변동"""
    return get_ranking_trends(days)

@app.get("/api/summary")
def api_summary():
    """DB 전체 요약"""
    return get_summary()

@app.get("/api/insights")
def api_insights():
    """AI 인사이트 생성"""
    trends = get_trends(14)
    ranking = get_ranking_trends(14)
    insights = []
    
    # 예약률 변동 분석
    if trends:
        dates = sorted(trends.keys())
        if len(dates) >= 2:
            for studio in ["스튜디오생일", "오늘우리 서현"]:
                recent_rates = []
                for d in dates[-7:]:
                    items = trends.get(d, {}).get(studio, [])
                    for item in items:
                        if item.get("rate", 0) > 0:
                            recent_rates.append(item["rate"])
                if recent_rates:
                    avg = sum(recent_rates) / len(recent_rates)
                    insights.append({
                        "type": "reservation",
                        "studio": studio,
                        "message": f"{studio} 최근 7일 평균 예약률: {avg:.0f}%",
                        "value": avg,
                    })
    
    # 순위 변동 분석
    for kw, data in ranking.items():
        if len(data) >= 2:
            current = data[-1]["rank"]
            prev = data[-2]["rank"]
            if current and prev:
                diff = prev - current  # positive = 상승
                if diff != 0:
                    direction = "🔼 상승" if diff > 0 else "🔽 하락"
                    insights.append({
                        "type": "ranking",
                        "keyword": kw,
                        "message": f"'{kw}' 순위 {direction} ({prev}위 → {current}위)",
                        "change": diff,
                    })
    
    if not insights:
        insights.append({
            "type": "info",
            "message": "📊 데이터 축적 중입니다. 2주 이후 의미 있는 인사이트가 생성됩니다.",
        })
    
    return insights

@app.get("/api/weekday-stats")
def api_weekday_stats():
    """요일별 평균 예약률"""
    db = get_db()
    cursor = db.execute("""
        SELECT 
            CASE strftime('%w', date)
                WHEN '0' THEN '일'
                WHEN '1' THEN '월'
                WHEN '2' THEN '화'
                WHEN '3' THEN '수'
                WHEN '4' THEN '목'
                WHEN '5' THEN '금'
                WHEN '6' THEN '토'
            END as weekday,
            studio,
            AVG(rate) as avg_rate,
            COUNT(*) as count
        FROM reservations
        WHERE rate > 0
        GROUP BY weekday, studio
        ORDER BY CAST(strftime('%w', date) AS INTEGER)
    """)
    rows = cursor.fetchall()
    db.close()
    
    result = {}
    for weekday, studio, avg_rate, count in rows:
        if weekday not in result:
            result[weekday] = {}
        result[weekday][studio] = {"avg_rate": round(avg_rate, 1), "count": count}
    return result

# ══════════════════════════════════════
# HTML 대시보드
# ══════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
def dashboard():
    html_path = os.path.join(os.path.dirname(__file__), "dashboard.html")
    if os.path.exists(html_path):
        with open(html_path, 'r') as f:
            return f.read()
    return "<h1>Dashboard HTML not found</h1>"

if __name__ == "__main__":
    import uvicorn
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    print(f"🚀 Dashboard: http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
