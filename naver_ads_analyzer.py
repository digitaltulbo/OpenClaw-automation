# -*- coding: utf-8 -*-
"""
Naver Ads API Analyzer (fixed)
Provides real keyword search volumes, CPC, competition level
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

def get_keyword_stats(keywords):
    """Get search volume & competition for multiple keywords"""
    creds = load_creds()
    base_url = "https://api.searchad.naver.com"
    uri = "/keywordstool"
    
    headers = get_header("GET", uri, creds['naver_ads_license'], creds['naver_ads_secret'], creds['naver_ads_customer_id'])
    
    if isinstance(keywords, str):
        keywords = [keywords]
    
    results = []
    # Filter out flags
    keywords = [k for k in keywords if not k.startswith('--')]
    
    results = []
    # Process one keyword at a time to avoid space issues
    for kw in keywords:
        # Remove internal spaces for hintKeywords  
        params = {"hintKeywords": kw, "showDetail": "1"}
        
        try:
            res = requests.get(base_url + uri, params=params, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json().get('keywordList', [])
                for item in data:
                    results.append({
                        "keyword": item.get('relKeyword', ''),
                        "pc_volume": item.get('monthlyPcQcCnt', 0),
                        "mobile_volume": item.get('monthlyMobileQcCnt', 0),
                        "total_volume": (item.get('monthlyPcQcCnt', 0) or 0) + (item.get('monthlyMobileQcCnt', 0) or 0),
                        "competition": item.get('compIdx', ''),
                        "avg_cpc": item.get('monthlyAvePcClkCnt', 0),
                    })
            else:
                results.append({"error": f"API {res.status_code}", "detail": res.text[:300]})
                print(f"DEBUG: status={res.status_code}, body={res.text[:500]}", file=__import__('sys').stderr)
        except Exception as e:
            results.append({"error": str(e)})
        
        time.sleep(0.3)
    
    return results

def format_report(results):
    msg = "📊 네이버 광고 키워드 분석\n"
    msg += "─" * 30 + "\n\n"
    
    for r in results:
        if "error" in r:
            msg += f"❌ {r['error']}\n"
            continue
        
        kw = r["keyword"]
        # API can return "< 10" or int
        pc = r.get("pc_volume", 0)
        mo = r.get("mobile_volume", 0)
        comp = r.get("competition", "")
        
        try:
            pc_int = int(pc) if isinstance(pc, int) else 0
            mo_int = int(mo) if isinstance(mo, int) else 0
            total = pc_int + mo_int
        except:
            total = 0
            pc_int = 0
            mo_int = 0
        
        if total > 0:
            bar_size = min(10, max(1, total // 500))
            bar = "▓" * bar_size + "░" * (10 - bar_size)
            msg += f"🔍 {kw}\n"
            msg += f"   검색량: {bar} {total:,}/월\n"
            msg += f"   (PC {pc_int:,} / 모바일 {mo_int:,})\n"
            msg += f"   경쟁도: {comp}\n\n"
        else:
            msg += f"🔍 {kw}: 검색량 {pc}/{mo}\n\n"
    
    return msg

if __name__ == "__main__":
    if len(sys.argv) > 1:
        keywords = sys.argv[1:]
    else:
        keywords = ["분당 셀프사진관", "야탑 사진관", "야탑 셀프사진관", "분당 가족사진", "분당 만삭사진"]
    
    results = get_keyword_stats(keywords)
    
    if "--json" in sys.argv:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(format_report(results))
