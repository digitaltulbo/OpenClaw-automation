# -*- coding: utf-8 -*-
"""
네이버 플레이스 소식 자동생성기 v1
- 미노출 키워드를 활용한 소식글 초안 생성
- 시즌별 맞춤 템플릿
- 텔레그램으로 전송하여 사용자 승인 후 복붙 게시
"""
import json, sys, datetime, subprocess, os, requests

SCRIPTS_DIR = '/home/openclaw/.openclaw/skills/seo-optimizer/scripts'
NOTIFY_BOT_TOKEN = '8465933562:AAFhXEjUd8Hzw5HwqVpwlUltSz4WdzdBPXQ'
CHAT_ID = '1385089848'

# ══════════════════════════════════════
# 시즌별 프로모션 매핑
# ══════════════════════════════════════
SEASON_THEMES = {
    1:  {"theme": "신년", "emoji": "🎍", "hook": "새해 첫 가족사진, 스튜디오생일에서 특별하게!"},
    2:  {"theme": "졸업", "emoji": "🎓", "hook": "졸업 시즌! 친구와 함께 추억을 남겨보세요"},
    3:  {"theme": "봄/입학", "emoji": "🌸", "hook": "입학 기념, 아이의 성장 기록을 남겨보세요"},
    4:  {"theme": "벚꽃/봄", "emoji": "🌷", "hook": "봄나들이 기념! 커플/가족 셀프사진 이벤트"},
    5:  {"theme": "가정의달", "emoji": "👨‍👩‍👧‍👦", "hook": "가정의 달, 가족과 함께하는 특별한 시간"},
    6:  {"theme": "여름", "emoji": "☀️", "hook": "여름방학 맞이! 아이와 함께 재미있는 사진 촬영"},
    7:  {"theme": "바캉스", "emoji": "🏖️", "hook": "바캉스 전에! 프로필 사진 업데이트하세요"},
    8:  {"theme": "만삭/돌잔치", "emoji": "🤰", "hook": "소중한 순간을 기록하세요. 만삭/돌 사진 촬영"},
    9:  {"theme": "가을", "emoji": "🍂", "hook": "가을 감성 가득한 프로필 사진을 찍어보세요"},
    10: {"theme": "할로윈", "emoji": "🎃", "hook": "할로윈 특별 촬영! 재미있는 컨셉 사진"},
    11: {"theme": "수능/연말", "emoji": "📸", "hook": "수능 끝! 친구와 함께 우정사진 촬영"},
    12: {"theme": "크리스마스", "emoji": "🎄", "hook": "연말 특별 이벤트! 크리스마스 컨셉 가족사진"},
}

# ══════════════════════════════════════
# 서비스별 키워드-컨텐츠 매핑
# ══════════════════════════════════════
SERVICE_TEMPLATES = {
    "우정사진": {
        "title_suffix": "친구와 함께하는 셀프사진",
        "body": "친구들과 함께 자유롭게 포즈를 잡고 촬영해보세요!\n셀프사진관이라 부담 없이 편하고 즐겁게 찍을 수 있어요.\n4컷 프레임도 즉석에서 만들어드립니다.",
        "tags": ["우정사진", "셀프사진관", "친구사진", "4컷"],
    },
    "프로필사진": {
        "title_suffix": "깔끔한 프로필 사진 촬영",
        "body": "이력서, SNS, 링크드인용 프로필 사진을 찍어보세요.\n전문 조명 아래에서 자연스럽고 깔끔한 사진을 얻으실 수 있어요.\n보정 포함, 당일 받기 가능!",
        "tags": ["프로필사진", "증명사진", "이력서사진", "분당"],
    },
    "가족사진": {
        "title_suffix": "온 가족이 함께하는 특별한 순간",
        "body": "아이 돌, 백일, 가족 기념일에 맞춰 자연스러운 가족사진을 남겨보세요.\n셀프사진관이라 아이가 편안하게 촬영할 수 있어요.",
        "tags": ["가족사진", "아기사진", "돌사진", "분당가족사진"],
    },
    "만삭사진": {
        "title_suffix": "소중한 만삭의 순간을 기록하세요",
        "body": "자연스럽고 아름다운 만삭 사진을 남겨보세요.\n편안한 분위기에서 원하는 만큼 촬영하실 수 있어요.",
        "tags": ["만삭사진", "임산부사진", "분당만삭", "야탑"],
    },
    "커플사진": {
        "title_suffix": "둘만의 특별한 순간",
        "body": "기념일, 데이트, 또는 그냥 특별한 하루를 사진으로 남겨보세요.\n셀프사진관이라 자유롭게 원하는 컨셉으로 촬영 가능!",
        "tags": ["커플사진", "데이트코스", "기념일사진", "야탑"],
    },
    "증명사진": {
        "title_suffix": "빠르고 깔끔한 증명사진",
        "body": "여권, 비자, 이력서용 증명사진을 찍어보세요.\n전문 조명과 배경으로 깔끔하게 촬영해드립니다.\n즉석 수령 가능!",
        "tags": ["증명사진", "여권사진", "야탑증명사진", "분당"],
    },
}

# 키워드에서 서비스 타입 매칭
KEYWORD_TO_SERVICE = {
    "우정": "우정사진",
    "프로필": "프로필사진",
    "가족": "가족사진",
    "만삭": "만삭사진",
    "커플": "커플사진",
    "증명": "증명사진",
    "여권": "증명사진",
    "백일": "가족사진",
    "돌잔치": "가족사진",
    "아기": "가족사진",
}

def get_unexposed_keywords():
    """keyword_discovery.py를 실행하여 미노출 키워드 가져오기"""
    try:
        cmd = ['python3', os.path.join(SCRIPTS_DIR, 'keyword_discovery.py'), '--json']
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        data = json.loads(res.stdout)
        return [kw for kw in data if not kw.get('exposed', True)]
    except:
        # Fallback: 하드코딩된 미노출 키워드
        return [
            {"keyword": "분당 우정사진", "exposed": False},
            {"keyword": "분당 프로필사진", "exposed": False},
        ]

def match_service(keyword):
    """키워드에서 서비스 타입을 추론"""
    kw_lower = keyword.lower()
    for key, service in KEYWORD_TO_SERVICE.items():
        if key in kw_lower:
            return service
    return "프로필사진"  # 기본값

def generate_post(keyword, season=None):
    """키워드 기반으로 소식글 초안 생성"""
    if season is None:
        season = datetime.date.today().month
    
    season_info = SEASON_THEMES.get(season, SEASON_THEMES[1])
    service = match_service(keyword)
    template = SERVICE_TEMPLATES.get(service, SERVICE_TEMPLATES["프로필사진"])
    
    # 지역명 추출
    location = ""
    for loc in ["분당", "야탑", "서현", "수내", "판교"]:
        if loc in keyword:
            location = loc
            break
    if not location:
        location = "분당"
    
    # 제목 생성
    title = f"{season_info['emoji']} {season_info['theme']} 시즌! {location}에서 {template['title_suffix']}"
    
    # 본문 생성
    body = f"{season_info['hook']}\n\n{template['body']}\n\n📍 스튜디오생일 ({location} 야탑역 도보 3분)"
    
    # 해시태그 생성
    base_tags = template["tags"]
    extra_tags = ["스튜디오생일", f"{location}셀프사진관"]
    kw_tag = keyword.replace(' ', '')
    if kw_tag not in base_tags:
        base_tags.insert(0, kw_tag)
    all_tags = list(dict.fromkeys(base_tags + extra_tags))  # 중복 제거
    hashtags = " ".join(f"#{t}" for t in all_tags[:8])
    
    return {
        "keyword": keyword,
        "service": service,
        "season": season_info["theme"],
        "title": title,
        "body": body,
        "hashtags": hashtags,
    }

def format_telegram_post(post, index=1):
    """텔레그램 전송용 포맷"""
    msg = f"📌 소식글 초안 #{index}\n"
    msg += "─" * 25 + "\n"
    msg += f"🎯 타겟 키워드: {post['keyword']}\n"
    msg += f"📂 서비스: {post['service']} | 시즌: {post['season']}\n\n"
    msg += f"📝 제목:\n{post['title']}\n\n"
    msg += f"🖊️ 본문:\n{post['body']}\n\n"
    msg += f"{post['hashtags']}\n"
    msg += "─" * 25 + "\n"
    msg += "💡 이 소식글을 네이버 플레이스에 올려보세요!\n"
    return msg

def format_report(posts):
    """전체 리포트 포맷"""
    msg = "✍️ 주간 소식글 초안\n"
    msg += "═" * 25 + "\n\n"
    
    for i, post in enumerate(posts, 1):
        msg += format_telegram_post(post, i) + "\n"
    
    msg += f"📋 총 {len(posts)}개 초안 | 복붙하여 네이버 플레이스 > 소식에 게시\n"
    return msg

def send_telegram(msg):
    """텔레그램으로 전송"""
    url = f"https://api.telegram.org/bot{NOTIFY_BOT_TOKEN}/sendMessage"
    if len(msg) > 4000:
        msg = msg[:3990] + "\n...(일부 생략)"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg}, timeout=15)
        return True
    except:
        return False

if __name__ == "__main__":
    # 미노출 키워드 가져오기
    if len(sys.argv) > 1 and not sys.argv[1].startswith('--'):
        # 수동 키워드 입력
        keywords = [{"keyword": k} for k in sys.argv[1:] if not k.startswith('--')]
    else:
        keywords = get_unexposed_keywords()
    
    if not keywords:
        print("ℹ️ 미노출 키워드가 없습니다. 모든 키워드에 노출 중!")
        sys.exit(0)
    
    # 소식글 생성 (최대 3개)
    posts = [generate_post(kw.get("keyword", kw) if isinstance(kw, dict) else kw) for kw in keywords[:3]]
    
    if "--json" in sys.argv:
        print(json.dumps(posts, ensure_ascii=False, indent=2))
    elif "--send" in sys.argv:
        send_telegram(format_report(posts))
        print(f"✅ {len(posts)}개 소식글 초안 전송됨")
    else:
        print(format_report(posts))
