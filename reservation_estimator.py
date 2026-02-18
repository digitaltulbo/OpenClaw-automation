# -*- coding: utf-8 -*-
"""
Reservation Rate Estimator v3 - Playwright
Clicks into Naver Place '예약' tab and extracts real time slots
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
    
    result = {"label": label, "place_id": place_id, "error": None, "reviews": {}, "slots": {}, "raw_booking": ""}
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
                viewport={"width": 390, "height": 844},
            )
            page = ctx.new_page()
            
            # Go directly to the booking tab URL
            url = f"https://m.place.naver.com/place/{place_id}/booking"
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(3000)
            
            # First, grab review counts from the page header
            text = page.inner_text('body')
            rv = re.search(r'방문자\s*리뷰\s*(\d+)', text)
            br = re.search(r'블로그\s*리뷰\s*(\d+)', text)
            if rv: result["reviews"]["visitor"] = int(rv.group(1))
            if br: result["reviews"]["blog"] = int(br.group(1))
            
            # Try clicking the actual reservation/booking link
            booking_clicked = False
            try:
                # Look for booking buttons or links
                booking_els = page.query_selector_all('a[href*="booking"], a[href*="reserve"], button:has-text("예약")')
                for el in booking_els:
                    txt = el.inner_text().strip()
                    if '예약' in txt:
                        el.click()
                        page.wait_for_timeout(3000)
                        booking_clicked = True
                        break
            except: pass
            
            if not booking_clicked:
                # Try the tab navigation
                try:
                    tabs = page.query_selector_all('[role="tab"], a[class*="tab"]')
                    for tab in tabs:
                        if '예약' in tab.inner_text():
                            tab.click()
                            page.wait_for_timeout(3000)
                            booking_clicked = True
                            break
                except: pass
            
            # Now extract booking data
            text = page.inner_text('body')
            
            # Look for time slots
            time_pattern = re.findall(r'(\d{1,2}:\d{2})', text)
            if time_pattern:
                result["raw_booking"] = f"시간대 발견: {', '.join(set(time_pattern))}"
            
            # Look for "마감" counts
            closed = len(re.findall(r'마감', text))
            avail = len(re.findall(r'예약\s*가능|선택\s*가능|예약하기', text))
            
            if closed + avail > 0:
                result["slots"]["closed"] = closed
                result["slots"]["available"] = avail
                result["slots"]["total"] = closed + avail
                result["slots"]["rate"] = round(closed / (closed + avail) * 100)
            
            # Try to find calendar/date with booking info
            # Extract the full booking page text for analysis
            result["raw_booking"] = text[:800]
            
            # Take a screenshot for debugging
            page.screenshot(path=f"/tmp/booking_{place_id}.png")
            
            browser.close()
    except Exception as e:
        result["error"] = str(e)
    
    return result

def format_report(results):
    msg = "📅 경쟁사 예약/리뷰 비교 리포트\n"
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
            msg += f"  📝 방문자리뷰: {v} | 블로그: {b}\n"
        
        # Slot data
        slots = r.get("slots", {})
        if slots and slots.get("total", 0) > 0:
            rate = slots["rate"]
            bar_filled = round(rate / 10)
            bar = "█" * bar_filled + "░" * (10 - bar_filled)
            msg += f"  📊 예약률: {bar} {rate}%\n"
            msg += f"     (마감 {slots['closed']} / 가능 {slots['available']})\n"
        
        if r.get("error"):
            msg += f"  ❌ {r['error'][:50]}\n"
        
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
        # Also print raw data for debugging
        for r in results:
            print(f"\n--- {r['label']} raw ---")
            print(r.get("raw_booking", "")[:300])
