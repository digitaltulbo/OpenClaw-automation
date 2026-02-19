# -*- coding: utf-8 -*-
"""
스튜디오 경쟁사 + 네이버 플레이스 설정
모든 스크립트가 이 파일을 참조하여 경쟁사 정보를 사용합니다.
"""

# ════ 우리 스튜디오 ════
OUR_STUDIO = {
    "id": "bday-yatap",
    "name": "스튜디오생일",
    "naver_place_id": "1234567890",  
    "place_url": "https://m.place.naver.com/place/1234567890",
    "keywords": ["야탑 셀프사진관", "야탑 사진관", "분당 셀프사진관"],
}

# ════ 경쟁사 5개 (야탑/분당 인접 지역) ════
COMPETITORS = [
    {
        "id": "onuluri-yatap",
        "name": "오늘우리 야탑",
        "dong": "야탑동",
        "address": "경기 성남시 분당구 야탑로 95 세신빌딩 7층",
        "distance": "야탑역 도보 3분",
        "note": "가장 직접적인 경쟁사, 50분 35,000원",
    },
    {
        "id": "bundang-self",
        "name": "분당셀프사진관",
        "dong": "야탑동",
        "address": "경기 성남시 분당구 야탑로 102",
        "distance": "야탑역 도보 5분",
        "note": "리뷰 117건, 10분/20분 단위 짧은 촬영 상품",
    },
    {
        "id": "yatap-village",
        "name": "야탑마을사진관",
        "dong": "야탑동",
        "address": "경기 성남시 분당구 야탑로69번길 18",
        "distance": "야탑역 도보 7분",
        "note": "리뷰 436건, 전통 사진관 + 셀프 옵션",
    },
    {
        "id": "photoism-yatap",
        "name": "포토이즘 야탑점",
        "dong": "야탑동",
        "address": "경기 성남시 분당구 야탑로81번길 10",
        "distance": "야탑역 도보 5분",
        "note": "무인 사진 부스 체인, MZ세대 고객층 겹침",
    },
    {
        "id": "urban-self",
        "name": "어반셀프사진관",
        "dong": "서현동(인접)",
        "address": "경기 성남시 분당구 서현로210번길 17",
        "distance": "야탑에서 차 5분",
        "note": "분당권 인기 셀프스튜디오, 세련된 인테리어",
    },
]

# ════ 텔레그램 설정 ════
TELEGRAM_BOT_TOKEN = '8465933562:AAFhXEjUd8Hzw5HwqVpwlUltSz4WdzdBPXQ'
TELEGRAM_CHAT_ID = '1385089848'

# ════ 편의 함수 ════
def get_competitor_names():
    return [c["name"] for c in COMPETITORS]

def get_all_studios():
    """우리 + 경쟁사 전체 목록"""
    return [OUR_STUDIO["name"]] + get_competitor_names()
