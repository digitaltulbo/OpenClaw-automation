# -*- coding: utf-8 -*-
"""
Studio Bday - Keyword Discovery
Finds related keywords from Naver's "함께 많이 찾는" section
Checks if we appear in each keyword's results
"""
import subprocess, re, json, urllib.parse, sys

TARGET = "스튜디오생일"
SEED_KEYWORDS = [
    "분당 셀프사진관",
    "야탑 셀프사진관",
]
# Hard-coded known related keywords from browser research
KNOWN_RELATED = [
    "분당 백일 셀프사진관",
    "분당 셀프사진관 만삭",
    "분당 셀프사진관 가족사진",
    "분당 셀프사진관 커플",
    "분당 아기 셀프사진관",
    "야탑 증명사진",
    "분당 우정사진",
    "분당 프로필사진",
]

def fetch_naver_html(keyword):
    encoded_kw = urllib.parse.quote(keyword)
    url = f"https://m.search.naver.com/search.naver?query={encoded_kw}"
    cmd = ["curl", "-s", "-L", "-A", "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)", url]
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout
    except: return ""

def find_related_keywords():
    """Combine scraped + known keywords"""
    found = set()
    for seed in SEED_KEYWORDS:
        html = fetch_naver_html(seed)
        # Extract from "함께 많이 찾는" section
        hm_pos = html.find('함께 많이 찾는')
        if hm_pos > 0:
            block = html[hm_pos:hm_pos+3000]
            matches = re.findall(r'>([^<]{4,40})<', block)
            for m in matches:
                m = m.strip()
                if len(m) > 3 and any(x in m for x in ['사진','스튜디오','셀프','분당','야탑']):
                    found.add(m)
        # Also try nx_query pattern
        nxq = re.findall(r'nx_query=[^"]*"[^>]*>([^<]{4,30})</a>', html)
        for kw in nxq:
            kw = kw.strip()
            if len(kw) > 3 and any(x in kw for x in ['사진','스튜디오','셀프','분당','야탑']):
                found.add(kw)
    
    # Add known keywords that haven't been found
    for kw in KNOWN_RELATED:
        found.add(kw)
    
    return list(found)[:15]

def check_presence(keyword):
    html = fetch_naver_html(keyword)
    return TARGET in html

def discover():
    keywords = find_related_keywords()
    results = []
    for kw in keywords:
        present = check_presence(kw)
        results.append({"keyword": kw, "we_appear": present, "opportunity": not present})
    # Sort: opportunities first
    results.sort(key=lambda x: (not x["opportunity"], x["keyword"]))
    return results

if __name__ == "__main__":
    if "--json" in sys.argv:
        print(json.dumps(discover(), ensure_ascii=False, indent=2))
    else:
        results = discover()
        print("🔑 주간 키워드 발굴 리포트")
        print("─" * 30)
        opps = [r for r in results if r["opportunity"]]
        covered = [r for r in results if not r["opportunity"]]
        
        if opps:
            print(f"\n🆕 미노출 키워드 ({len(opps)}개) - 공략 기회!")
            for r in opps:
                print(f"  ❌ '{r['keyword']}'")
            print(f"\n💡 위 키워드들은 검색 시 우리가 노출되지 않습니다.")
            print("   플레이스 태그/소식에 포함하면 유입 가능!")
        
        if covered:
            print(f"\n✅ 노출 중 ({len(covered)}개)")
            for r in covered:
                print(f"  ✅ '{r['keyword']}'")
        
        if not results:
            print("   (발견된 연관 키워드가 없습니다.)")
