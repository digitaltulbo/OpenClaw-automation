# -*- coding: utf-8 -*-
"""
리뷰 자동 응답 초안 생성기 v1
- 네이버 플레이스 리뷰를 크롤링
- 새 리뷰 감지 시 AI 답글 초안 생성
- 텔레그램으로 초안 전송 (사장님 승인 후 수동 게시)

사용법:
  python3 review_monitor.py           # 새 리뷰 체크 + 답글 초안 생성
  python3 review_monitor.py --test    # 테스트 (샘플 리뷰로 답글 생성)
"""
import requests, json, os, sys, re, datetime, hashlib

# ── 설정 ──
NOTIFY_BOT_TOKEN = '8465933562:AAFhXEjUd8Hzw5HwqVpwlUltSz4WdzdBPXQ'
CHAT_ID = '1385089848'
PLACE_ID = '1234567890'  # 네이버 플레이스 ID (naver_rank_checker.py와 동일)
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
SEEN_FILE = os.path.join(SCRIPTS_DIR, 'seen_reviews.json')

# ── 리뷰 응답 템플릿 ──
TEMPLATES = {
    "positive_5": [
        "안녕하세요, 스튜디오생일입니다 🎂\n소중한 후기 감사합니다! {감사포인트}\n다음에도 좋은 추억 남기실 수 있도록 더 노력하겠습니다.\n또 방문해주세요! 💕",
        "안녕하세요, 스튜디오생일입니다 ✨\n좋은 리뷰 남겨주셔서 정말 감사해요! {감사포인트}\n언제든 편하게 찾아주세요 📸",
    ],
    "positive_4": [
        "안녕하세요, 스튜디오생일입니다 🎂\n따듯한 리뷰 감사합니다! {감사포인트}\n더 좋은 경험을 드릴 수 있도록 노력하겠습니다 💛",
    ],
    "neutral_3": [
        "안녕하세요, 스튜디오생일입니다.\n리뷰 남겨주셔서 감사합니다. {개선의지}\n더 나은 서비스로 보답하겠습니다. 감사합니다 🙏",
    ],
    "negative_12": [
        "안녕하세요, 스튜디오생일입니다.\n불편을 드려 죄송합니다. {공감포인트}\n말씀해주신 부분은 즉시 개선하도록 하겠습니다.\n다음에 방문해주시면 더 좋은 경험을 드리겠습니다. 🙏",
    ],
}

# ── 리뷰 분석 키워드 ──
POSITIVE_KEYWORDS = ['좋아요', '만족', '추천', '깔끔', '친절', '예쁘', '넓', '최고', '좋았', '만족스', '재밌', '사진 잘', '보정', '인테리어']
NEGATIVE_KEYWORDS = ['별로', '실망', '좁', '불편', '더럽', '비싸', '아쉬', '불친절', '시끄', '어둡', '짧', '안내 부족']
SERVICE_KEYWORDS = {
    '조명': ['조명', '라이트', '빛'],
    '공간': ['넓', '공간', '인테리어', '깨끗', '깔끔'],
    '소품': ['소품', '의상', '배경'],
    '보정': ['보정', 'AI', '사진 퀄리티'],
    '가격': ['가격', '가성비', '비싸', '저렴'],
    '접근성': ['위치', '역', '주차', '찾기'],
}


def load_seen():
    """이미 처리한 리뷰 ID 목록 로드"""
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, 'r') as f:
            return json.load(f)
    return {"seen": [], "last_check": None}


def save_seen(data):
    data["last_check"] = str(datetime.datetime.now())
    # 최근 500개만 유지
    data["seen"] = data["seen"][-500:]
    with open(SEEN_FILE, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def review_id(review):
    """리뷰 고유 ID 생성 (작성자 + 내용 해시)"""
    raw = f"{review.get('author','')}{review.get('body','')[:50]}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def fetch_reviews_via_api():
    """네이버 플레이스 리뷰 API (비공식)"""
    url = f"https://api.place.naver.com/graphql"
    # GraphQL query for visitor reviews
    query = {
        "operationName": "getVisitorReviews",
        "variables": {
            "input": {
                "businessId": PLACE_ID,
                "bookingBusinessId": PLACE_ID,
                "page": 1,
                "size": 10,
                "isPhotoUsed": False,
                "item": "0",
                "theme": "0",
                "includeContent": True,
                "getUserPhotos": True,
                "includeReceiptPhotos": True,
            },
            "id": PLACE_ID,
        },
        "query": """query getVisitorReviews($input: VisitorReviewsInput) {
            visitorReviews(input: $input) {
                items {
                    id body created rating
                    author { nickname }
                }
                total
            }
        }"""
    }
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
        "Referer": f"https://m.place.naver.com/place/{PLACE_ID}/review",
    }
    try:
        r = requests.post(url, json=query, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            items = data.get("data", {}).get("visitorReviews", {}).get("items", [])
            reviews = []
            for item in items:
                reviews.append({
                    "id": item.get("id", ""),
                    "author": item.get("author", {}).get("nickname", "익명"),
                    "body": item.get("body", ""),
                    "rating": item.get("rating", 0),
                    "created": item.get("created", ""),
                })
            return reviews
        else:
            print(f"API error: {r.status_code}")
            return []
    except Exception as e:
        print(f"Fetch error: {e}")
        return []


def analyze_review(review):
    """리뷰 분석: 감정, 키워드, 서비스 카테고리"""
    body = review.get("body", "")
    rating = review.get("rating", 0)
    
    # 감정 분석
    pos_count = sum(1 for kw in POSITIVE_KEYWORDS if kw in body)
    neg_count = sum(1 for kw in NEGATIVE_KEYWORDS if kw in body)
    
    # 서비스 카테고리 매칭
    mentioned_services = []
    for service, keywords in SERVICE_KEYWORDS.items():
        if any(kw in body for kw in keywords):
            mentioned_services.append(service)
    
    # 감정 결정
    if rating >= 5 or (rating >= 4 and pos_count > neg_count):
        sentiment = "positive"
    elif rating <= 2 or neg_count > pos_count:
        sentiment = "negative"
    else:
        sentiment = "neutral"
    
    return {
        "sentiment": sentiment,
        "rating": rating,
        "pos_keywords": pos_count,
        "neg_keywords": neg_count,
        "services": mentioned_services,
    }


def generate_reply(review, analysis):
    """리뷰에 맞는 답글 초안 생성"""
    import random
    body = review.get("body", "")
    rating = analysis["rating"]
    sentiment = analysis["sentiment"]
    services = analysis["services"]
    
    # 템플릿 선택
    if rating >= 5:
        templates = TEMPLATES["positive_5"]
    elif rating >= 4:
        templates = TEMPLATES["positive_4"]
    elif rating >= 3:
        templates = TEMPLATES["neutral_3"]
    else:
        templates = TEMPLATES["negative_12"]
    
    template = random.choice(templates)
    
    # 맥락에 맞는 감사/공감 포인트 생성
    if sentiment == "positive":
        points = []
        if "조명" in services: points.append("조명이 마음에 드셨다니 기쁩니다")
        if "공간" in services: points.append("넓은 공간에서 편하게 촬영하셨다니 다행이에요")
        if "소품" in services: points.append("소품도 활용해주셔서 감사해요")
        if "보정" in services: points.append("보정 결과가 만족스러우셨다니 보람을 느낍니다")
        if "가격" in services: points.append("합리적인 가격이라 느끼셨다니 감사합니다")
        if "접근성" in services: points.append("찾아오시기 편하셨다니 좋습니다")
        
        if not points:
            points = ["좋은 시간 보내셨다니 정말 기쁩니다"]
        
        감사포인트 = "\n".join(points[:2])
        reply = template.replace("{감사포인트}", 감사포인트)
    elif sentiment == "negative":
        points = []
        if "공간" in services: points.append("공간 관련 불편을 드려 죄송합니다")
        if "가격" in services: points.append("가격 부분 고려하여 이벤트를 준비하겠습니다")
        if "조명" in services: points.append("조명 환경을 개선하도록 하겠습니다")
        
        if not points:
            points = ["불편하셨던 부분을 개선하기 위해 최선을 다하겠습니다"]
        
        공감포인트 = "\n".join(points[:2])
        reply = template.replace("{공감포인트}", 공감포인트)
    else:
        reply = template.replace("{개선의지}", "더 좋은 서비스를 위해 지속적으로 노력하겠습니다")
    
    return reply


def send_telegram(msg):
    url = f"https://api.telegram.org/bot{NOTIFY_BOT_TOKEN}/sendMessage"
    if len(msg) > 4000:
        msg = msg[:3990] + "\n...(일부 생략)"
    try:
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": msg}, timeout=15)
        return r.status_code == 200
    except:
        return False


def process_new_reviews():
    """새 리뷰 확인 → 답글 생성 → 텔레그램 전송"""
    seen_data = load_seen()
    seen_ids = set(seen_data["seen"])
    
    reviews = fetch_reviews_via_api()
    if not reviews:
        print("리뷰를 가져올 수 없거나 새 리뷰가 없습니다.")
        return
    
    new_reviews = []
    for r in reviews:
        rid = r.get("id") or review_id(r)
        if rid not in seen_ids:
            new_reviews.append(r)
            seen_data["seen"].append(rid)
    
    if not new_reviews:
        print(f"새 리뷰 없음 (마지막 체크: {seen_data.get('last_check', '초기')})")
        save_seen(seen_data)
        return
    
    # 새 리뷰에 대한 답글 초안 생성
    msg = f"📝 신규 리뷰 {len(new_reviews)}건 감지!\n"
    msg += "═" * 28 + "\n"
    
    for i, review in enumerate(new_reviews, 1):
        analysis = analyze_review(review)
        reply = generate_reply(review, analysis)
        
        # 감정 이모지
        emoji = "😊" if analysis["sentiment"] == "positive" else "😐" if analysis["sentiment"] == "neutral" else "😟"
        stars = "⭐" * analysis["rating"]
        
        msg += f"\n📌 리뷰 #{i} ({emoji} {stars})\n"
        msg += f"─────────────────\n"
        msg += f"👤 {review['author']}\n"
        
        body = review['body']
        if len(body) > 150:
            body = body[:150] + "..."
        msg += f"💬 \"{body}\"\n"
        
        if analysis["services"]:
            msg += f"🏷️ 관련: {', '.join(analysis['services'])}\n"
        
        msg += f"\n✍️ 추천 답글:\n"
        msg += f"───\n{reply}\n───\n"
        msg += f"💡 위 답글을 네이버 플레이스에 복붙하세요!\n"
    
    msg += f"\n{'─' * 28}\n"
    msg += f"🔔 리뷰 자동 답글 | {datetime.datetime.now().strftime('%H:%M')}"
    
    success = send_telegram(msg)
    save_seen(seen_data)
    
    if success:
        print(f"✅ {len(new_reviews)}건 리뷰 답글 텔레그램 전송 완료")
    else:
        print(f"❌ 텔레그램 전송 실패")


def test_mode():
    """테스트 모드 — 샘플 리뷰로 답글 생성 확인"""
    sample_reviews = [
        {
            "id": "test-1",
            "author": "행복한사진러버",
            "body": "조명이 정말 예쁘고 공간도 넓어서 편하게 찍었어요! 보정도 마음에 들었습니다. 가격도 합리적이에요. 다음에 친구들과 또 올게요!",
            "rating": 5,
            "created": str(datetime.datetime.now()),
        },
        {
            "id": "test-2",
            "author": "분당맘",
            "body": "아이랑 같이 갔는데 소품이 많아서 좋았어요. 위치가 역에서 가까워서 찾기 쉬웠습니다.",
            "rating": 4,
            "created": str(datetime.datetime.now()),
        },
        {
            "id": "test-3",
            "author": "솔직후기",
            "body": "공간은 괜찮은데 가격이 좀 비싼 것 같아요. 시간이 좀 짧게 느껴졌습니다.",
            "rating": 3,
            "created": str(datetime.datetime.now()),
        },
    ]
    
    msg = f"🧪 리뷰 답글 테스트 ({len(sample_reviews)}건)\n"
    msg += "═" * 28 + "\n"
    
    for i, review in enumerate(sample_reviews, 1):
        analysis = analyze_review(review)
        reply = generate_reply(review, analysis)
        
        emoji = "😊" if analysis["sentiment"] == "positive" else "😐" if analysis["sentiment"] == "neutral" else "😟"
        stars = "⭐" * analysis["rating"]
        
        msg += f"\n📌 리뷰 #{i} ({emoji} {stars})\n"
        msg += f"─────────────────\n"
        msg += f"👤 {review['author']}\n"
        msg += f"💬 \"{review['body'][:150]}\"\n"
        
        if analysis["services"]:
            msg += f"🏷️ 키워드: {', '.join(analysis['services'])}\n"
        
        msg += f"\n✍️ 추천 답글:\n"
        msg += f"───\n{reply}\n───\n"
    
    msg += f"\n{'─' * 28}\n"
    msg += f"🧪 테스트 완료 — 실제 리뷰가 아닌 샘플입니다"
    
    success = send_telegram(msg)
    print(f"테스트 {'성공' if success else '실패'}")
    return msg


if __name__ == "__main__":
    if "--test" in sys.argv:
        test_mode()
    else:
        process_new_reviews()
