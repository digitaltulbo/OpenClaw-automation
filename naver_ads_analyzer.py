# -*- coding: utf-8 -*-
"""
Naver Ads API Analyzer v2
- Keywords with spaces are stripped before API call
- Handles '< 10' string values from API
- Only returns the searched keyword's data (not related keywords)
"""
import requests, time, hmac, hashlib, base64, json, sys

def load_creds():
    with open('/home/openclaw/.openclaw/credentials/naver.json', 'r') as f:
        return json.load(f)

def get_header(method, uri, api_key, secret_key, customer_id):
    timestamp = str(round(time.time() * 1000))
    signature_str = f"{timestamp}.{method}.{uri}"
    sig = hmac.HMAC(secret_key.encode(), signature_str.encode(), hashlib.sha256).digest()
    return {
        "Content-Type": "application/json",
        "X-Timestamp": timestamp,
        "X-API-KEY": api_key,
        "X-Customer": str(customer_id),
        "X-Signature": base64.b64encode(sig).decode()
    }

def safe_int(val):
    """Convert API value to int, handle '< 10' strings"""
    if isinstance(val, int):
        return val
    if isinstance(val, str):
        try:
            return int(val.replace('<', '').replace('>', '').strip())
        except:
            return 0
    return 0

def get_keyword_stats(keywords):
    """Get search volume & competition for keywords"""
    creds = load_creds()
    base_url = "https://api.searchad.naver.com"
    uri = "/keywordstool"
    
    headers = get_header("GET", uri, creds['naver_ads_license'], creds['naver_ads_secret'], creds['naver_ads_customer_id'])
    
    if isinstance(keywords, str):
        keywords = [keywords]
    
    # Filter out flags
    keywords = [k for k in keywords if not k.startswith('--')]
    
    results = []
    for kw in keywords:
        # Remove spaces for API compatibility
        api_kw = kw.replace(' ', '')
        params = {"hintKeywords": api_kw, "showDetail": "1"}
        
        try:
            res = requests.get(base_url + uri, params=params, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json().get('keywordList', [])
                # Only return the exact keyword match + top 3 related
                matched = None
                related = []
                for item in data:
                    rk = item.get('relKeyword', '')
                    pc = safe_int(item.get('monthlyPcQcCnt', 0))
                    mo = safe_int(item.get('monthlyMobileQcCnt', 0))
                    entry = {
                        "keyword": rk,
                        "pc_volume": pc,
                        "mobile_volume": mo,
                        "total_volume": pc + mo,
                        "competition": item.get('compIdx', ''),
                    }
                    # Match: exact or space-stripped match
                    if rk.replace(' ', '') == api_kw:
                        matched = entry
                    elif len(related) < 3:
                        related.append(entry)
                
                if matched:
                    results.append(matched)
                # Add up to 2 related keywords
                results.extend(related[:2])
            else:
                results.append({"keyword": kw, "error": f"API {res.status_code}"})
        except Exception as e:
            results.append({"keyword": kw, "error": str(e)[:50]})
        
        time.sleep(0.3)
    
    return results

def format_report(results):
    msg = "📊 네이버 키워드 분석\n"
    msg += "─" * 28 + "\n"
    
    for r in results:
        if "error" in r:
            msg += f"❌ {r.get('keyword','?')}: {r['error']}\n"
            continue
        
        kw = r["keyword"]
        pc = r.get("pc_volume", 0)
        mo = r.get("mobile_volume", 0)
        total = r.get("total_volume", 0)
        comp = r.get("competition", "")
        
        if total > 0:
            bar_size = min(10, max(1, total // 500))
            bar = "▓" * bar_size + "░" * (10 - bar_size)
            msg += f"\n🔍 {kw}\n"
            msg += f"   {bar} {total:,}/월 (PC {pc:,} / M {mo:,})\n"
            msg += f"   경쟁도: {comp}\n"
        else:
            msg += f"\n🔍 {kw}: < 10건/월\n"
    
    return msg

if __name__ == "__main__":
    if len(sys.argv) > 1:
        keywords = [k for k in sys.argv[1:] if not k.startswith('--')]
    else:
        keywords = ["분당 셀프사진관", "야탑 사진관", "야탑 셀프사진관", "분당 가족사진", "분당 만삭사진"]
    
    results = get_keyword_stats(keywords)
    
    if "--json" in sys.argv:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(format_report(results))
