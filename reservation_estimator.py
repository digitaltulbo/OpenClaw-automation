# -*- coding: utf-8 -*-
"""
Reservation Rate Estimator v6
- Uses Playwright click navigation (not regex URL parsing)
- Goes Place page → clicks 예약 tab → clicks booking service → extracts slots
- Only today + tomorrow
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
    
    result = {"label": label, "place_id": place_id, "reviews": {}, "days": [], "error": None}
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
                viewport={"width": 800, "height": 900},
            )
            page = ctx.new_page()
            
            # Step 1: Go to Place page (not /booking, main page)
            page.goto(f"https://m.place.naver.com/place/{place_id}/home", wait_until="networkidle", timeout=20000)
            page.wait_for_timeout(2000)
            
            # Extract reviews
            text = page.inner_text('body')
            rv = re.search(r'방문자\s*리뷰\s*(\d+)', text)
            br = re.search(r'블로그\s*리뷰\s*(\d+)', text)
            if rv: result["reviews"]["visitor"] = int(rv.group(1))
            if br: result["reviews"]["blog"] = int(br.group(1))
            
            # Step 2: Click the "예약" tab/button to get to booking
            booking_found = False
            
            # Method 1: Look for booking.naver.com link in rendered DOM
            try:
                links = page.query_selector_all('a')
                for link in links:
                    href = link.get_attribute('href') or ''
                    if 'booking.naver.com' in href:
                        page.goto(href, wait_until="networkidle", timeout=15000)
                        page.wait_for_timeout(3000)
                        booking_found = True
                        break
            except: pass
            
            # Method 2: Click the 예약 tab text
            if not booking_found:
                try:
                    tabs = page.query_selector_all('a, button, span')
                    for tab in tabs:
                        txt = tab.inner_text().strip()
                        if txt == '예약':
                            tab.click()
                            page.wait_for_timeout(3000)
                            
                            # After clicking, look for booking.naver.com link again
                            links2 = page.query_selector_all('a')
                            for link2 in links2:
                                href2 = link2.get_attribute('href') or ''
                                if 'booking.naver.com' in href2:
                                    page.goto(href2, wait_until="networkidle", timeout=15000)
                                    page.wait_for_timeout(3000)
                                    booking_found = True
                                    break
                            if booking_found: break
                            
                            # Or check if we're already on booking page
                            if 'booking.naver.com' in page.url:
                                booking_found = True
                                break
                except: pass
            
            # Method 3: Direct URL construction
            if not booking_found:
                try:
                    page.goto(f"https://m.place.naver.com/place/{place_id}/booking", wait_until="networkidle", timeout=15000)
                    page.wait_for_timeout(3000)
                    
                    # Click any element that leads to booking.naver.com
                    els = page.query_selector_all('a[href*="booking"], [class*="booking"], [class*="reserve"]')
                    if els:
                        els[0].click()
                        page.wait_for_timeout(3000)
                        booking_found = 'booking.naver.com' in page.url
                    
                    # Try clicking "예약" button within the page
                    if not booking_found:
                        btns = page.query_selector_all('a, button')
                        for btn in btns:
                            try:
                                txt = btn.inner_text().strip()
                                href = btn.get_attribute('href') or ''
                                if ('예약' in txt and len(txt) < 20) or 'booking.naver.com' in href:
                                    if 'booking.naver.com' in href:
                                        page.goto(href, wait_until="networkidle", timeout=15000)
                                    else:
                                        btn.click()
                                    page.wait_for_timeout(3000)
                                    booking_found = True
                                    break
                            except: continue
                except: pass
            
            if not booking_found:
                result["error"] = "booking_page_unreachable"
                browser.close()
                return result
            
            # Step 3: Now on booking.naver.com - extract today's slots
            today_data = extract_slots(page)
            today_data["date"] = str(datetime.date.today())
            today_data["day_label"] = "오늘"
            result["days"].append(today_data)
            
            # Step 4: Click tomorrow on calendar
            tomorrow = datetime.date.today() + datetime.timedelta(days=1)
            try:
                date_els = page.query_selector_all('.calendar_date:not(.unselectable):not(.prev_month):not(.next_month)')
                for el in date_els:
                    if el.inner_text().strip() == str(tomorrow.day):
                        el.click()
                        page.wait_for_timeout(1500)
                        tmr_data = extract_slots(page)
                        tmr_data["date"] = str(tomorrow)
                        tmr_data["day_label"] = "내일"
                        result["days"].append(tmr_data)
                        break
            except Exception as e:
                result["days"].append({"date": str(tomorrow), "day_label": "내일", "error": str(e)[:50]})
            
            browser.close()
    except Exception as e:
        result["error"] = str(e)[:100]
    
    return result

def extract_slots(page):
    data = {"total": 0, "booked": 0, "available": 0, "rate": 0, "slots": []}
    try:
        all_btns = page.query_selector_all('.btn_time, button[class*="btn_time"]')
        for btn in all_btns:
            time_text = btn.inner_text().strip()
            if ':' not in time_text: continue
            cls = btn.get_attribute('class') or ''
            is_booked = 'unselectable' in cls or btn.get_attribute('disabled') is not None
            data["slots"].append({"time": time_text, "booked": is_booked})
        
        if data["slots"]:
            data["total"] = len(data["slots"])
            data["booked"] = sum(1 for s in data["slots"] if s["booked"])
            data["available"] = data["total"] - data["booked"]
            data["rate"] = round(data["booked"] / data["total"] * 100) if data["total"] > 0 else 0
    except Exception as e:
        data["error"] = str(e)[:50]
    return data

def format_report(results):
    msg = "📅 예약 현황 비교\n"
    for r in results:
        icon = "👉" if "스튜디오" in r["label"] else "🎯"
        msg += f"\n{icon} {r['label']}"
        rv = r.get("reviews", {})
        if rv:
            msg += f" (리뷰 {rv.get('visitor','?')})"
        msg += "\n"
        
        if r.get("error"):
            msg += f"  ❌ {r['error']}\n"
            continue
        
        for day in r.get("days", []):
            lbl = day.get("day_label", day.get("date",""))
            if "error" in day:
                msg += f"  {lbl}: ❌\n"
                continue
            if day.get("total", 0) > 0:
                rate = day["rate"]
                bar = "█" * round(rate/10) + "░" * (10-round(rate/10))
                msg += f"  {lbl}: {bar} {rate}% ({day['booked']}마감/{day['total']}전체)\n"
                booked_times = [s["time"] for s in day.get("slots",[]) if s["booked"]]
                avail_times = [s["time"] for s in day.get("slots",[]) if not s["booked"]]
                if booked_times:
                    msg += f"    ❌ 마감: {', '.join(booked_times)}\n"
                if avail_times:
                    msg += f"    ✅ 가능: {', '.join(avail_times)}\n"
            else:
                msg += f"  {lbl}: ℹ️ 슬롯 데이터 없음\n"
    return msg

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{NOTIFY_BOT_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": CHAT_ID, "text": msg}, timeout=10)
    except: pass

if __name__ == "__main__":
    results = [check_booking(pid, label) for label, pid in PLACES.items()]
    if "--json" in sys.argv:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    elif "--send" in sys.argv:
        send_telegram(format_report(results))
        print("Sent!")
    else:
        print(format_report(results))
