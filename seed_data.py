# -*- coding: utf-8 -*-
"""
Seed sample data for dashboard demo.
Creates 14 days of realistic reservation, ranking, and keyword data.
"""
import sqlite3, json, datetime, os, sys, random

# Use local path
DB_PATH = os.path.join(os.path.dirname(__file__), 'studio_data.db')

def seed():
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA journal_mode=WAL")
    
    # Create tables
    db.execute("""CREATE TABLE IF NOT EXISTS reservations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL, collected_at TEXT NOT NULL, studio TEXT NOT NULL,
        day_label TEXT, total_slots INTEGER DEFAULT 0, booked_slots INTEGER DEFAULT 0,
        available_slots INTEGER DEFAULT 0, rate REAL DEFAULT 0,
        booked_times TEXT, available_times TEXT,
        visitor_reviews INTEGER DEFAULT 0, blog_reviews INTEGER DEFAULT 0
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS rankings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL, collected_at TEXT NOT NULL, keyword TEXT NOT NULL,
        our_rank INTEGER, competitors TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS keyword_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL, keyword TEXT NOT NULL,
        pc_volume INTEGER DEFAULT 0, mobile_volume INTEGER DEFAULT 0,
        total_volume INTEGER DEFAULT 0, competition TEXT
    )""")
    
    # Clear old data
    db.execute("DELETE FROM reservations")
    db.execute("DELETE FROM rankings")
    db.execute("DELETE FROM keyword_stats")
    
    today = datetime.date.today()
    random.seed(42)
    
    studios = {
        "스튜디오생일": {"base_rate": 35, "reviews_start": 245, "review_per_day": 0.8},
        "오늘우리 야탑": {"base_rate": 25, "reviews_start": 110, "review_per_day": 0.5},
        "오늘우리 서현": {"base_rate": 55, "reviews_start": 800, "review_per_day": 1.2},
    }
    
    keywords_ranking = {
        "분당 셀프사진관": {"base_rank": 3, "variance": 1},
        "야탑 사진관": {"base_rank": 2, "variance": 1},
        "야탑 셀프사진관": {"base_rank": 1, "variance": 0},
    }
    
    # Generate 14 days of data
    for day_offset in range(14, -1, -1):
        d = today - datetime.timedelta(days=day_offset)
        date_str = str(d)
        weekday = d.weekday()
        
        # Weekend boost factor
        weekend_boost = 1.5 if weekday >= 5 else 1.0
        
        for studio, config in studios.items():
            # Reservations - today and tomorrow
            for label in ["오늘", "내일"]:
                total = random.choice([12, 13])
                rate = min(95, max(0, config["base_rate"] * weekend_boost + random.randint(-15, 25)))
                booked = round(total * rate / 100)
                available = total - booked
                
                all_times = ["9:00","10:00","11:00","12:00","1:00","2:00","3:00","4:00","5:00","6:00","7:00","8:00"]
                if total == 13: all_times.append("9:00")
                booked_times = random.sample(all_times[:total], min(booked, total))
                avail_times = [t for t in all_times[:total] if t not in booked_times]
                
                reviews = round(config["reviews_start"] + config["review_per_day"] * (14 - day_offset))
                
                db.execute("""INSERT INTO reservations 
                    (date, collected_at, studio, day_label, total_slots, booked_slots, available_slots, rate, booked_times, available_times, visitor_reviews, blog_reviews)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (date_str, f"{date_str}T09:00:00", studio, label,
                     total, booked, available, round(rate, 1),
                     json.dumps(booked_times, ensure_ascii=False),
                     json.dumps(avail_times, ensure_ascii=False),
                     reviews, round(reviews * 0.3)))
        
        # Rankings
        for kw, config in keywords_ranking.items():
            rank = max(1, config["base_rank"] + random.randint(-config["variance"], config["variance"]))
            competitors = [
                {"rank": 1, "name": "유어포토"},
                {"rank": 2, "name": "YEY 스튜디오"},
                {"rank": rank, "name": "스튜디오생일"},
                {"rank": 4, "name": "유어포토 셀프사진관"},
            ]
            db.execute("""INSERT INTO rankings (date, collected_at, keyword, our_rank, competitors)
                VALUES (?,?,?,?,?)""",
                (date_str, f"{date_str}T09:00:00", kw, rank,
                 json.dumps(competitors, ensure_ascii=False)))
    
    # Keyword stats (weekly)
    for d_offset in [14, 7, 0]:
        d = today - datetime.timedelta(days=d_offset)
        for kw, pc, mo, comp in [
            ("분당셀프사진관", 50, 320, "중간"),
            ("야탑사진관", 70, 590, "중간"),
            ("야탑셀프사진관", 10, 100, "중간"),
            ("분당가족사진", 340, 580, "높음"),
            ("분당프로필사진", 20, 120, "높음"),
        ]:
            db.execute("""INSERT INTO keyword_stats (date, keyword, pc_volume, mobile_volume, total_volume, competition)
                VALUES (?,?,?,?,?,?)""",
                (str(d), kw, pc, mo, pc+mo, comp))
    
    db.commit()
    
    count = db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]
    rcount = db.execute("SELECT COUNT(*) FROM rankings").fetchone()[0]
    kcount = db.execute("SELECT COUNT(*) FROM keyword_stats").fetchone()[0]
    db.close()
    
    print(f"✅ Seeded: {count} reservations, {rcount} rankings, {kcount} keyword stats")
    print(f"📍 DB: {DB_PATH}")

if __name__ == "__main__":
    seed()
