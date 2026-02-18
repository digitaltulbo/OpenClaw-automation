# -*- coding: utf-8 -*-
"""
Studio Bday - Reservation Rate Estimator
Checks competitor Naver Place booking pages
to estimate availability rates across time slots

Targets:
  - 스튜디오생일 (us)
  - 오늘, 우리 사진관 분당야탑 (main competitor)
  - 오늘, 우리 사진관 분당서현 (competitor)
"""
import subprocess, re, json, sys, datetime, urllib.parse

# Naver Place IDs (from naver.me links or place URLs)
# These need to be set to actual Place IDs
PLACES = {
    "스튜디오생일": {
        "place_id": "",  # Will be discovered
        "search_name": "스튜디오생일 야탑",
    },
    "오늘우리 야탑": {
        "place_id": "",
        "search_name": "오늘우리사진관 야탑",
    },
    "오늘우리 서현": {
        "place_id": "",
        "search_name": "오늘우리사진관 서현",
    },
}

def fetch_url(url):
    cmd = ["curl", "-s", "-L", "-A", "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)", url]
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout
    except: return ""

def discover_place_ids():
    """Find Naver Place IDs from search results"""
    results = {}
    for label, info in PLACES.items():
        kw = urllib.parse.quote(info["search_name"])
        url = f"https://m.search.naver.com/search.naver?query={kw}"
        html = fetch_url(url)

        # Extract place ID from the first place_bluelink href
        match = re.search(r'place\.naver\.com/place/(\d+)', html)
        if match:
            results[label] = match.group(1)
    return results

def check_booking_availability(place_id, target_date=None):
    """Check a Naver Place booking page for available/unavailable slots"""
    if not target_date:
        target_date = datetime.date.today()
    
    date_str = target_date.strftime("%Y-%m-%d")
    
    # Naver Place booking/reservation page
    url = f"https://m.place.naver.com/place/{place_id}/booking"
    html = fetch_url(url)
    
    if not html:
        return {"error": "fetch_failed", "slots": []}
    
    # Check if booking is available at all
    if '예약' not in html and 'booking' not in html.lower():
        return {"error": "no_booking_system", "slots": []}
    
    # Try to find time slot data in embedded JSON
    # Naver often embeds booking data in script tags
    slots_data = []
    
    # Pattern: Look for time slot objects
    time_matches = re.findall(r'"time":\s*"(\d{2}:\d{2})".*?"available":\s*(true|false)', html, re.DOTALL)
    if time_matches:
        for time_str, avail in time_matches:
            slots_data.append({
                "time": time_str,
                "available": avail == "true"
            })
    
    # Alternative: count available/total from booking widget text
    if not slots_data:
        # Check for "마감" or "예약가능" text patterns
        closed_count = len(re.findall(r'마감', html))
        available_count = len(re.findall(r'예약\s*가능|선택\s*가능', html))
        
        if closed_count > 0 or available_count > 0:
            total = closed_count + available_count
            return {
                "date": date_str,
                "total_slots": total,
                "closed_slots": closed_count,
                "available_slots": available_count,
                "booking_rate": round(closed_count / max(total, 1) * 100),
                "raw": True
            }
    
    if slots_data:
        total = len(slots_data)
        booked = sum(1 for s in slots_data if not s["available"])
        return {
            "date": date_str,
            "total_slots": total,
            "closed_slots": booked,
            "available_slots": total - booked,
            "booking_rate": round(booked / max(total, 1) * 100),
            "slots": slots_data
        }
    
    return {"date": date_str, "error": "no_slot_data", "html_length": len(html)}

def run_estimation():
    """Main estimation routine"""
    place_ids = discover_place_ids()
    
    results = {}
    for label, pid in place_ids.items():
        if pid:
            # Check today and next 3 days
            days_data = []
            for offset in range(4):
                target = datetime.date.today() + datetime.timedelta(days=offset)
                data = check_booking_availability(pid, target)
                days_data.append(data)
            results[label] = {"place_id": pid, "days": days_data}
        else:
            results[label] = {"error": "place_id_not_found"}
    
    return results

def format_report(results):
    msg = "📅 예약률 추정 리포트\n"
    msg += "─" * 30 + "\n"
    
    for label, data in results.items():
        if "error" in data:
            msg += f"\n{label}: ❌ {data['error']}\n"
            continue
        
        msg += f"\n📍 {label} (Place ID: {data['place_id']})\n"
        for day in data["days"]:
            if "error" in day:
                date = day.get("date", "?")
                msg += f"  {date}: {day['error']}\n"
            else:
                rate = day.get("booking_rate", 0)
                bar_filled = round(rate / 10)
                bar = "█" * bar_filled + "░" * (10 - bar_filled)
                msg += f"  {day['date']}: {bar} {rate}%\n"
    
    return msg

if __name__ == "__main__":
    if "--discover" in sys.argv:
        ids = discover_place_ids()
        for label, pid in ids.items():
            print(f"{label}: {pid or 'not found'}")
    elif "--json" in sys.argv:
        print(json.dumps(run_estimation(), ensure_ascii=False, indent=2))
    else:
        results = run_estimation()
        print(format_report(results))
