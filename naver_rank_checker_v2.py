# -*- coding: utf-8 -*-
import subprocess, re, sys, json, urllib.parse

TARGET = "스튜디오생일"
COMPETITORS = ["오늘, 우리 사진관", "오늘우리"]
KEYWORDS = ["분당 셀프사진관", "야탑 사진관", "야탑 셀프사진관"]

def strip_html(text):
    """Remove ALL HTML tags and entities from text"""
    text = re.sub(r'<[^>]+>', '', text)           # <mark>, </mark>, etc.
    text = re.sub(r'\\u003[Cc][^;]*;?', '', text) # unicode escaped tags
    text = re.sub(r'&[a-zA-Z]+;', '', text)       # &amp; etc.
    return text.strip()

def fetch_naver_html(keyword):
    encoded_kw = urllib.parse.quote(keyword)
    url = f"https://m.search.naver.com/search.naver?query={encoded_kw}"
    cmd = ["curl", "-s", "-L", "-A", "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)", url]
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout
    except: return ""

def parse_place_rankings(html):
    rankings = []
    seen_names = set()
    
    items = html.split('<li class="BX')[1:]
    for block in items[:20]:
        name_search = re.search(r'<span>([^<]+)</span>', block)
        if not name_search: continue
        raw_name = name_search.group(1).strip()
        name = strip_html(raw_name)
        
        if not name or name in ['MY','변경','더보기','네이버']: continue
        if 'place_bluelink' not in block and 'tit' not in block: continue
        if name in seen_names: continue  # Skip duplicates
        seen_names.add(name)

        is_us = TARGET in name
        is_competitor = any(c in name for c in COMPETITORS)
        
        review_count = 0
        rv_match = re.search(r'(?:리뷰|방문자리뷰)\s*(\d+,?\d*)', block)
        if rv_match:
            try: review_count = int(rv_match.group(1).replace(',',''))
            except: pass
            
        rankings.append({
            "rank": len(rankings) + 1,
            "name": name,
            "reviews": review_count,
            "is_us": is_us,
            "is_competitor": is_competitor
        })
        if len(rankings) >= 10: break
    
    if not rankings:
        matches = re.findall(r'"name":"([^"]+)"', html)
        for raw in matches[:50]:
            name = strip_html(raw)
            if name in seen_names: continue
            if any(x in name for x in ['사진','스튜디오','포토','셀프']):
                seen_names.add(name)
                rankings.append({"rank": len(rankings)+1, "name": name, "reviews": 0,
                    "is_us": TARGET in name, "is_competitor": any(c in name for c in COMPETITORS)})
                if len(rankings) >= 10: break
    return rankings

if __name__ == "__main__":
    if "--json" in sys.argv:
        results = []
        for kw in KEYWORDS:
            ranks = parse_place_rankings(fetch_naver_html(kw))
            our = next((r["rank"] for r in ranks if r["is_us"]), 0)
            results.append({"keyword": kw, "our_rank": our, "rankings": ranks})
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for kw in KEYWORDS:
            ranks = parse_place_rankings(fetch_naver_html(kw))
            print(f"\n📌 '{kw}' 검색 결과:")
            if not ranks: print("  (데이터 없음)")
            for item in ranks:
                marker = " 👉 우리" if item["is_us"] else (" 🎯" if item["is_competitor"] else "")
                rev = f" (리뷰 {item['reviews']})" if item['reviews'] > 0 else ""
                print(f"  {item['rank']}위: {item['name']}{rev}{marker}")
