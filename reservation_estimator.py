# -*- coding: utf-8 -*-
"""
Reservation Rate Estimator v4 - Precise Naver Booking Scraper
Uses exact selectors discovered from browser inspection:
  - btn_time => available slot
  - btn_time unselectable => booked slot
  - calendar_date => selectable date
  - calendar_date dayoff => holiday/closed
"""
import json, sys, datetime, re, requests

PLACES = {
    "스튜디오생일": "1210788398",
    "오늘우리 야탑": "2048985540",
    "오늘우리 서현": "1391677364",
}
NOTIFY_BOT_TOKEN = '8465933562:AAFhXEjUd8Hzw5HwqVpwlUltSz4WdzdBPXQ'
CHAT_ID = '1385089848'

def check_booking(place_id, label):
    from playwright.sync_api import sync_playwright
    
    result = {
        "label": label,
        "place_id": place_id,
        "reviews": {},
        "booking_url": None,
        "days": [],
        "error": None,
    }
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
                viewport={"width": 800, "height": 900},
            )
            page = ctx.new_page()
            
            # Step 1: Go to Place booking tab
            url = f"https://m.place.naver.com/place/{place_id}/booking"
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(2000)
            
            # Extract review counts
            text = page.inner_text('body')
            rv = re.search(r'방문자\s*리뷰\s*(\d+)', text)
            br = re.search(r'블로그\s*리뷰\s*(\d+)', text)
            if rv: result["reviews"]["visitor"] = int(rv.group(1))
            if br: result["reviews"]["blog"] = int(br.group(1))
            
            # Step 2: Click the booking service item (e.g. "셀프촬영 예약", "50분의 셀프 촬영")
            booking_links = page.query_selector_all('a[href*="booking.naver.com"]')
            booking_url = None
            
            if not booking_links:
                # Try clicking any 예약 button
                reserve_btns = page.query_selector_all('a:has-text("예약"), button:has-text("예약")')
                for btn in reserve_btns:
                    href = btn.get_attribute('href')
                    if href and 'booking.naver.com' in href:
                        booking_url = href
                        break
            else:
                booking_url = booking_links[0].get_attribute('href')
            
            if not booking_url:
                # Last resort: find booking URL in page source
                content = page.content()
                bk_match = re.search(r'(https://booking\.naver\.com/booking/[^"\']+)', content)
                if bk_match:
                    booking_url = bk_match.group(1)
            
            if not booking_url:
                result["error"] = "booking_url_not_found"
                browser.close()
                return result
            
            result["booking_url"] = booking_url
            
            # Step 3: Navigate to the booking widget
            page.goto(booking_url, wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(3000)
            
            # Step 4: Extract data for multiple dates
            # First, get today's slots
            today_data = extract_slots(page)
            today_data["date"] = str(datetime.date.today())
            result["days"].append(today_data)
            
            # Click through next few dates on the calendar
            for offset in range(1, 5):
                target_date = datetime.date.today() + datetime.timedelta(days=offset)
                
                # Try clicking the calendar date
                day_num = target_date.day
                try:
                    # Find all calendar_date elements
                    date_els = page.query_selector_all('.calendar_date:not(.unselectable):not(.prev_month):not(.next_month)')
                    for el in date_els:
                        el_text = el.inner_text().strip()
                        if el_text == str(day_num):
                            el.click()
                            page.wait_for_timeout(1500)
                            day_data = extract_slots(page)
                            day_data["date"] = str(target_date)
                            result["days"].append(day_data)
                            break
                except Exception as e:
                    result["days"].append({"date": str(target_date), "error": str(e)[:50]})
            
            browser.close()
    except Exception as e:
        result["error"] = str(e)[:100]
    
    return result

def extract_slots(page):
    """Extract time slots from the current booking page state"""
    data = {"total": 0, "booked": 0, "available": 0, "rate": 0, "slots": []}
    
    try:
        # Find all time buttons
        all_btns = page.query_selector_all('.btn_time, button[class*="btn_time"]')
        
        for btn in all_btns:
            time_text = btn.inner_text().strip()
            if ':' not in time_text:
                continue
            
            cls = btn.get_attribute('class') or ''
            is_booked = 'unselectable' in cls
            disabled = btn.get_attribute('disabled')
            
            data["slots"].append({
                "time": time_text,
                "booked": is_booked or disabled is not None,
            })
        
        if data["slots"]:
            data["total"] = len(data["slots"])
            data["booked"] = sum(1 for s in data["slots"] if s["booked"])
            data["available"] = data["total"] - data["booked"]
            data["rate"] = round(data["booked"] / data["total"] * 100) if data["total"] > 0 else 0
    except Exception as e:
        data["error"] = str(e)[:50]
    
    return data

def format_report(results):
    msg = "📅 경쟁사 예약률 비교 리포트\n"
    msg += f"📆 {datetime.date.today()}\n"
    msg += "═" * 28 + "\n\n"
    
    for r in results:
        icon = "👉" if "스튜디오" in r["label"] else "🎯"
        msg += f"{icon} {r['label']}\n"
        
        # Reviews
        rv = r.get("reviews", {})
        if rv:
            v = rv.get("visitor", "?")
            b = rv.get("blog", "?")
            msg += f"  📝 리뷰: 방문자 {v} / 블로그 {b}\n"
        
        if r.get("error"):
            msg += f"  ❌ {r['error']}\n\n"
            continue
        
        # Per-day data
        for day in r.get("days", []):
            if "error" in day:
                msg += f"  {day['date']}: ❌ {day['error']}\n"
                continue
            
            if day.get("total", 0) > 0:
                rate = day["rate"]
                bar_filled = round(rate / 10)
                bar = "█" * bar_filled + "░" * (10 - bar_filled)
                msg += f"  {day['date']}: {bar} {rate}%"
                msg += f" ({day['booked']}마감/{day['total']}전체)\n"
                
                # Show slot details
                for s in day.get("slots", []):
                    st = "❌" if s["booked"] else "✅"
                    msg += f"    {st} {s['time']}\n"
            else:
                msg += f"  {day['date']}: ℹ️ 슬롯 데이터 없음\n"
        msg += "\n"
    
    return msg

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{NOTIFY_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg}, timeout=10)
    except: pass

if __name__ == "__main__":
    results = [check_booking(pid, label) for label, pid in PLACES.items()]
    
    if "--json" in sys.argv:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    elif "--send" in sys.argv:
        msg = format_report(results)
        send_telegram(msg)
        print("Sent!")
    else:
        print(format_report(results))
