#!/usr/bin/env python3
"""
스튜디오생일 자동화 스크립트 v6.0
- 구글 캘린더 → 구글 시트 자동 등록 (신규)
- 원본/내보내기 정리
- 베이직/프리미엄 시트 분리 운영
- 베이직: 원본 ZIP → 업로드 → 발송
- 프리미엄: 1차(원본+구글폼) / 2차(보정본) 발송
- EXIF 촬영일 검증 (90% 기준)
- Drive/Sheets: OAuth 토큰 방식 (bdayyatap@gmail.com)
- Firebase Storage: bdaystudio.store API 경유
"""

import os
import sys
import json
import re
import shutil
import zipfile
import pickle
import logging
import requests
import firebase_admin
from firebase_admin import credentials as fb_credentials, storage as fb_storage
from pathlib import Path
from datetime import datetime, timedelta, timezone
from PIL import Image
from PIL.ExifTags import TAGS

from google.oauth2.service_account import Credentials as ServiceCredentials
from google.oauth2.credentials import Credentials as OAuthCredentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# ============================================================
# 설정
# ============================================================
ORIGINAL_FOLDER = Path('/volume2/photo/BDAY-STUDIO/C/Original/원본사진')
EXPORT_FOLDER = Path('/volume2/photo/BDAY-STUDIO/C/Users/zepss/Desktop/내보내기')
CLIENTS_FOLDER = Path('/volume2/photo/BDAY-STUDIO/C/Console')
PREMIUM_FOLDER = Path('/volume2/photo/WORK/01 프리미엄 고객')
PREMIUM_DONE_FOLDER = PREMIUM_FOLDER / '01 발송완료'
ORIGINAL_BASE = Path('/volume2/photo/BDAY-STUDIO/C/Original/원본사진')
RETOUCH_SUBFOLDER = '보정본'

CREDENTIALS_FILE = Path.home() / 'studio_automation' / 'scripts' / 'credentials.json'
TOKEN_FILE = Path.home() / 'studio_automation' / 'scripts' / 'drive_token.pickle'
CONFIG_FILE = Path.home() / 'studio_automation' / 'scripts' / 'config.json'
LOG_FILE = Path('/var/services/homes/jin/studio_automation/logs/auto_organizer.log')
LOCK_FILE = Path('/var/services/homes/jin/studio_automation/scripts/auto_organizer.lock')
CALENDAR_ID = 'bdayyatap@gmail.com'

PAST_HOURS_LIMIT = 6
TIME_BUFFER_MINUTES = 10
KST = timezone(timedelta(hours=9))

# 시트 범위 (기존 시트1은 건드리지 않음)
BASIC_SHEET_RANGE = '베이직!A2:F1000'
PREMIUM_SHEET_RANGE = '프리미엄!A2:J1000'

SCOPES_CALENDAR = ['https://www.googleapis.com/auth/calendar.readonly']
SCOPES_OAUTH = [
    'https://www.googleapis.com/auth/spreadsheets'
]

# ============================================================
# 로깅 설정
# ============================================================
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(str(LOG_FILE), encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ============================================================
# 설정 파일 로드
# ============================================================
def load_config():
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

# ============================================================
# API 서비스 생성
# ============================================================
def get_calendar_service():
    creds = ServiceCredentials.from_service_account_file(
        str(CREDENTIALS_FILE), scopes=SCOPES_CALENDAR
    )
    service = build('calendar', 'v3', credentials=creds, cache_discovery=False)
    logger.info("Google Calendar API 연결 성공")
    return service

def get_oauth_credentials():
    creds = None
    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, 'rb') as f:
            creds = pickle.load(f)
    if creds and creds.expired and creds.refresh_token:
        logger.info("OAuth 토큰 갱신 중...")
        creds.refresh(Request())
        with open(TOKEN_FILE, 'wb') as f:
            pickle.dump(creds, f)
        logger.info("OAuth 토큰 갱신 완료")
    if not creds or not creds.valid:
        error_msg = "OAuth 토큰이 유효하지 않습니다. 맥미니에서 토큰을 재생성해야 자동화가 재개됩니다."
        logger.error(error_msg)
        try:
            config = load_config()
            notify_error(config, "인증 도구", error_msg)
        except:
            pass
        return None
    return creds

def get_sheets_service():
    creds = get_oauth_credentials()
    if not creds:
        raise Exception("OAuth 인증 실패")
    sheets_service = build('sheets', 'v4', credentials=creds, cache_discovery=False)
    logger.info("Google Sheets API 연결 성공 (OAuth)")
    return sheets_service

def init_firebase():
    """Firebase Admin SDK 초기화"""
    if firebase_admin._apps:
        return fb_storage.bucket()
    
    scripts_dir = Path.home() / 'studio_automation' / 'scripts'
    pid = (scripts_dir / 'fb_project_id.txt').read_text().strip()
    email = (scripts_dir / 'fb_client_email.txt').read_text().strip()
    pk = (scripts_dir / 'fb_private_key.txt').read_text().strip().replace('\\n', '\n')
    
    cred = fb_credentials.Certificate({
        'type': 'service_account',
        'project_id': pid,
        'client_email': email,
        'private_key': pk,
        'token_uri': 'https://oauth2.googleapis.com/token'
    })
    firebase_admin.initialize_app(cred, {'storageBucket': pid + '.firebasestorage.app'})
    bucket = fb_storage.bucket()
    logger.info(f"Firebase Storage 연결 성공: {bucket.name}")
    return bucket

# ============================================================
# 보조 함수
# ============================================================
def sanitize_customer_name(name):
    if not name:
        return "unknown"
    clean = re.sub(r'\(.*?\)', '', name).strip()
    clean = re.sub(r'[^\w가-힣a-zA-Z0-9 ]', '', clean).strip()
    return clean if clean else "unknown"

def normalize_date(date_str):
    """'2026. 2. 13' → '260213'"""
    parts = re.split(r'[\./\-\s]+', date_str.strip())
    parts = [p for p in parts if p]
    if len(parts) == 3:
        y = parts[0][-2:]
        m = parts[1].zfill(2)
        d = parts[2].zfill(2)
        return f"{y}{m}{d}"
    if len(parts) == 2:
        # 2개 부품만 있으면 현재 연도 가정 (예: '2/15')
        y = str(datetime.now(KST).year)[-2:]
        m = parts[0].zfill(2)
        d = parts[1].zfill(2)
        return f"{y}{m}{d}"
    return ""

def get_exif_date(filepath):
    """JPG 파일의 EXIF DateTimeOriginal에서 날짜 추출 → 'YYYY-MM-DD'"""
    try:
        img = Image.open(filepath)
        exif = img._getexif()
        if exif:
            for tag_id, value in exif.items():
                if TAGS.get(tag_id) == 'DateTimeOriginal':
                    return value[:10].replace(':', '-')
    except Exception:
        pass
    return None

def validate_exif_dates(source_folder, shoot_date, customer_name):
    """EXIF 촬영일 검증: 전체 사진 중 90% 이상 날짜 일치해야 통과"""
    all_jpg = list(source_folder.rglob('*.jpg')) + list(source_folder.rglob('*.JPG'))
    all_jpg = [f for f in all_jpg if '@eaDir' not in str(f) and not f.name.startswith('.')]
    if not all_jpg:
        return True, 0, 0  # 사진 없으면 통과 (다음 단계에서 스킵됨)

    # shoot_date를 YYYY-MM-DD 형식으로 변환
    normalized = normalize_date(shoot_date)
    if len(normalized) == 6:
        target_date = f"20{normalized[:2]}-{normalized[2:4]}-{normalized[4:6]}"
    else:
        target_date = None

    if not target_date:
        logger.warning(f"{customer_name}: 촬영일 파싱 불가 → EXIF 검증 스킵")
        return True, len(all_jpg), 0

    match_count = 0
    for jpg in all_jpg:
        exif_date = get_exif_date(jpg)
        if exif_date == target_date:
            match_count += 1

    total = len(all_jpg)
    ratio = match_count / total if total > 0 else 0
    pct = int(ratio * 100)
    folder_name = source_folder.name

    if ratio >= 0.9:
        logger.info(f"[검증 통과] {customer_name} | 촬영일: {normalized} | 폴더: {folder_name} | 사진: {total}장 | EXIF 날짜 일치: {match_count}/{total} ({pct}%)")
        return True, total, match_count
    else:
        logger.warning(f"[검증 실패] {customer_name} | 촬영일: {normalized} | 폴더: {folder_name} | EXIF 날짜 일치: {match_count}/{total} ({pct}%) → 스킵")
        return False, total, match_count

def is_name_match(masked_name, full_name):
    if masked_name == full_name:
        return True
    if len(masked_name) >= 2 and len(full_name) >= 2:
        if masked_name in full_name or full_name in masked_name:
            return True
    if '*' in masked_name:
        pattern = masked_name.replace('*', '.')
        if re.match(pattern, full_name):
            return True
    if '*' in full_name:
        pattern = full_name.replace('*', '.')
        if re.match(pattern, masked_name):
            return True
    if len(masked_name) >= 2 and len(full_name) >= 2:
        if masked_name[0] == full_name[0] and masked_name[-1] == full_name[-1]:
            return True
    return False

def create_customer_folder(base_folder, date_str, customer_name):
    folder_name = f"{date_str}_{customer_name}"
    folder_path = base_folder / folder_name
    folder_path.mkdir(parents=True, exist_ok=True)
    return folder_path

def parse_google_time(time_str):
    try:
        if 'T' in time_str:
            if '+' in time_str or time_str.endswith('Z'):
                dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            else:
                dt = datetime.fromisoformat(time_str).replace(tzinfo=KST)
            return dt.astimezone(KST)
    except Exception as e:
        logger.warning(f"시간 파싱 실패: {time_str} - {e}")
    return None

def parse_export_filename_time(filename):
    match = re.search(r'(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})', filename)
    if match:
        try:
            return datetime(
                int(match.group(1)), int(match.group(2)), int(match.group(3)),
                int(match.group(4)), int(match.group(5)), int(match.group(6)),
                tzinfo=KST
            )
        except ValueError:
            pass
    return None

# ============================================================
# Phase 1: 원본/내보내기 정리
# ============================================================
def scan_photo_folder(folder, label=""):
    if not folder.exists():
        logger.warning(f"{label} 폴더 없음: {folder}")
        return []
    files = []
    for f in folder.iterdir():
        if f.is_file() and not f.name.startswith('.') and not f.name.startswith('@'):
            files.append(f)
    logger.info(f"{label}: {len(files)}개 파일 발견")
    return files

def move_photos_for_appointment(files, start_time, end_time, dest_folder, label=""):
    buffer = timedelta(minutes=TIME_BUFFER_MINUTES)
    range_start = start_time - buffer
    range_end = end_time + buffer
    moved = 0
    for f in files:
        try:
            file_time = parse_export_filename_time(f.name)
            if file_time is None:
                mtime = os.path.getmtime(str(f))
                file_time = datetime.fromtimestamp(mtime, tz=KST)
            if range_start <= file_time <= range_end:
                dest = dest_folder / f.name
                counter = 1
                while dest.exists():
                    stem = f.stem
                    dest = dest_folder / f"{stem}_{counter}{f.suffix}"
                    counter += 1
                shutil.move(str(f), str(dest))
                moved += 1
        except Exception as e:
            logger.error(f"파일 이동 실패 {f.name}: {e}")
    if moved > 0:
        logger.info(f"{label}: {moved}장 이동 완료 → {dest_folder.name}")
    return moved

def process_appointments(service):
    now = datetime.now(KST)
    time_min = (now - timedelta(hours=PAST_HOURS_LIMIT)).isoformat()
    time_max = (now + timedelta(hours=PAST_HOURS_LIMIT)).isoformat()
    try:
        events_result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=time_min, timeMax=time_max,
            singleEvents=True, orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])
    except Exception as e:
        logger.error(f"캘린더 조회 실패: {e}")
        return []
    if not events:
        logger.info("예약 없음")
        return []
    events.reverse()
    original_files = scan_photo_folder(ORIGINAL_FOLDER, "원본사진")
    export_files = scan_photo_folder(EXPORT_FOLDER, "내보내기")
    total_original = 0
    total_export = 0
    processed_events = []
    for event in events:
        summary = event.get('summary', 'unknown')
        start_str = event.get('start', {}).get('dateTime', '')
        end_str = event.get('end', {}).get('dateTime', '')
        start_time = parse_google_time(start_str)
        end_time = parse_google_time(end_str)
        if not start_time or not end_time:
            logger.warning(f"시간 파싱 실패, 건너뜀: {summary}")
            continue
        customer_name = sanitize_customer_name(summary)
        date_str = start_time.strftime('%y%m%d')
        grade = '프리미엄' if ('프리미엄' in summary or 'premium' in summary.lower()) else '베이직'
        folder_label = f"{customer_name}_{grade}"
        customer_folder = create_customer_folder(CLIENTS_FOLDER, date_str, folder_label)
        orig_moved = move_photos_for_appointment(
            original_files, start_time, end_time,
            customer_folder, f"원본→{customer_name}"
        )
        total_original += orig_moved
        export_subfolder = customer_folder / '내보내기'
        export_subfolder.mkdir(exist_ok=True)
        exp_moved = move_photos_for_appointment(
            export_files, start_time, end_time,
            export_subfolder, f"내보내기→{customer_name}"
        )
        total_export += exp_moved
        processed_events.append({
            'summary': summary, 'customer_name': customer_name,
            'start_time': start_time, 'end_time': end_time, 'date_str': date_str
        })
    logger.info(f"정리 완료: 원본 {total_original}장, 내보내기 {total_export}장 이동")
    return processed_events

# ============================================================
# Phase 2: 베이직/프리미엄 발송 조회
# ============================================================
def get_pending_basic(sheets_service, config):
    """베이직 시트에서 D열(리뷰확인) 체크 있고 E열(원본발송) 비어있는 건 조회"""
    sheet_id = config['ledger_sheet_id']
    try:
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=sheet_id, range=BASIC_SHEET_RANGE
        ).execute()
        rows = result.get('values', [])
    except Exception as e:
        logger.error(f"베이직 시트 조회 실패: {e}")
        return []
    pending = []
    for i, row in enumerate(rows):
        shoot_date = row[0].strip() if len(row) > 0 else ''
        customer_name = row[1].strip() if len(row) > 1 else ''
        phone = row[2].strip() if len(row) > 2 else ''
        review_done = row[3].strip() if len(row) > 3 else ''
        original_sent = row[4].strip() if len(row) > 4 else ''
        if customer_name and review_done and not original_sent:
            if not phone:
                logger.info(f"{customer_name}: 전화번호 미입력 → 발송 대기")
                continue
            pending.append({
                'row_index': i + 2,
                'customer_name': customer_name,
                'phone': phone,
                'shoot_date': shoot_date,
            })
    logger.info(f"베이직 발송 대기: {len(pending)}건")
    return pending

def get_pending_premium(sheets_service, config):
    """프리미엄 시트에서 1차/2차 발송 대기 건 조회
    컬럼: A:촬영일, B:고객이름, C:전화번호, D:주소,
          E:1차발송(원본+구글폼), F:보정요청일, G:보정완료,
          H:2차발송(보정본), I:최종컨펌일, J:비고
    """
    sheet_id = config['ledger_sheet_id']
    try:
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=sheet_id, range=PREMIUM_SHEET_RANGE
        ).execute()
        rows = result.get('values', [])
    except Exception as e:
        logger.error(f"프리미엄 시트 조회 실패: {e}")
        return [], []
    first_pending = []   # 1차 발송 대기
    second_pending = []  # 2차 발송 대기
    for i, row in enumerate(rows):
        shoot_date = row[0].strip() if len(row) > 0 else ''
        customer_name = row[1].strip() if len(row) > 1 else ''
        phone = row[2].strip() if len(row) > 2 else ''
        address = row[3].strip() if len(row) > 3 else ''
        first_sent = row[4].strip() if len(row) > 4 else ''    # E열: 1차발송
        retouch_done = row[6].strip() if len(row) > 6 else ''  # G열: 보정완료
        second_sent = row[7].strip() if len(row) > 7 else ''   # H열: 2차발송
        # 1차: 1차발송(E열) 비어있는 건 (전화번호 없으면 스킵)
        if customer_name and not first_sent and not phone:
            logger.info(f"{customer_name}: 전화번호 미입력 → 발송 대기")
        elif customer_name and phone and not first_sent:
            first_pending.append({
                'row_index': i + 2,
                'customer_name': customer_name,
                'phone': phone,
                'shoot_date': shoot_date,
                'address': address,
                'delivery_type': 'first',
            })
        # 2차: 보정완료(G열)에 값 있고 2차발송(H열) 비어있는 건
        if customer_name and retouch_done and not second_sent:
            second_pending.append({
                'row_index': i + 2,
                'customer_name': customer_name,
                'phone': phone,
                'shoot_date': shoot_date,
                'address': address,
                'delivery_type': 'second',
            })
    logger.info(f"프리미엄 1차 발송 대기: {len(first_pending)}건, 2차 발송 대기: {len(second_pending)}건")
    return first_pending, second_pending

def find_delivery_folder(customer_name, shoot_date=None, delivery_type='original'):
    """발송용 폴더 탐색: delivery_type 에 따라 '내보내기' 또는 '보정본' 우선 탐색"""
    normalized_shoot = normalize_date(shoot_date) if shoot_date else ''
    
    # 1순위: Console 폴더 (주로 베이직/프리미엄 1차 원본)
    # 2순위: 프리미엄 작업 폴더 (주로 프리미엄 2차 보정본)
    search_paths = [CLIENTS_FOLDER, PREMIUM_FOLDER]
    
    for base_folder in search_paths:
        if not base_folder.exists():
            continue
            
        for folder in base_folder.iterdir():
            if not folder.is_dir() or folder.name.startswith('@') or folder.name.startswith('0'):
                continue
            
            # 날짜 매칭
            folder_date = folder.name[:6]
            if normalized_shoot and folder_date != normalized_shoot:
                continue
            
            # 이름 매칭
            folder_parts = re.sub(r'^\d{6}_', '', folder.name).strip()
            folder_customer = re.split(r'[\s_]', folder_parts)[0].strip()
            
            if is_name_match(customer_name, folder_customer):
                # delivery_type에 따른 하위 폴더 우선 순위
                if delivery_type == 'retouched':
                    target_sub = folder / RETOUCH_SUBFOLDER  # '보정본'
                else:
                    target_sub = folder / '내보내기'
                
                if target_sub.exists():
                    jpgs = list(target_sub.glob('*.jpg')) + list(target_sub.glob('*.JPG'))
                    jpgs = [f for f in jpgs if not f.name.startswith('.')]
                    if jpgs:
                        logger.info(f"대상 폴더 발견 ({delivery_type}): {folder.name}/{target_sub.name} ({len(jpgs)}장)")
                        return target_sub
                
                # 차선책: 다른 하위 폴더도 확인
                other_sub = folder / '내보내기' if delivery_type == 'retouched' else folder / RETOUCH_SUBFOLDER
                if other_sub.exists():
                    jpgs = list(other_sub.glob('*.jpg')) + list(other_sub.glob('*.JPG'))
                    jpgs = [f for f in jpgs if not f.name.startswith('.')]
                    if jpgs:
                        logger.info(f"대상 폴더 발견 (차선): {folder.name}/{other_sub.name} ({len(jpgs)}장)")
                        return other_sub

                # 마지막 수단: 폴더 전체 탐색
                all_jpg = list(folder.rglob('*.jpg')) + list(folder.rglob('*.JPG'))
                all_jpg = [f for f in all_jpg if '@eaDir' not in str(f) and not f.name.startswith('.')]
                if all_jpg:
                    logger.info(f"대상 폴더 발견 (전체 탐색): {folder.name} ({len(all_jpg)}장)")
                    return folder
    
    logger.warning(f"발송 대상 폴더 없음: {customer_name} ({delivery_type})")
    return None

def zip_folder(folder_path, zip_name):
    """하위 폴더 구조를 보존하며 ZIP 생성"""
    zip_path = Path('/tmp') / zip_name
    logger.info(f"ZIP 압축 시작: {folder_path} → {zip_path}")
    with zipfile.ZipFile(str(zip_path), 'w', zipfile.ZIP_DEFLATED) as zf:
        for file in sorted(folder_path.rglob('*')):
            if file.is_file() and '@eaDir' not in str(file) and not file.name.startswith('.'):
                arcname = file.relative_to(folder_path)
                zf.write(str(file), str(arcname))
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    logger.info(f"ZIP 생성 완료: {zip_name} ({size_mb:.0f}MB)")
    return zip_path

def upload_to_firebase(bucket, zip_path, customer_name):
    """Firebase Storage에 직접 업로드"""
    blob_path = f"auto/{customer_name}/{zip_path.name}"
    blob = bucket.blob(blob_path)
    
    logger.info(f"Firebase Storage 업로드 시작: {zip_path.name} ({zip_path.stat().st_size / (1024*1024):.0f}MB)")
    
    blob.upload_from_filename(str(zip_path), content_type='application/zip')
    
    # 서명된 다운로드 URL 생성 (15일 유효)
    from datetime import timedelta as td
    url = blob.generate_signed_url(expiration=td(days=15), method='GET')
    
    logger.info(f"Firebase 업로드 완료: {blob_path}")
    return url

def create_download_page(config, customer_name, shoot_date, original_url, page_type='original'):
    """bdaystudio.store에 고객 다운로드 페이지 자동 생성"""
    api_url = config['bdaystudio_api_url']
    api_key = config['bdaystudio_api_key']
    create_url = f"{api_url}/api/auto-create"
    
    # shoot_date 형식 변환 → YYYY-MM-DD (공백/점/하이픈/슬래시 모두 처리)
    import re as _re
    digits = _re.sub(r'[^0-9]', '', shoot_date)
    if len(digits) == 6:
        formatted_date = f"20{digits[:2]}-{digits[2:4]}-{digits[4:6]}"
    elif len(digits) == 8:
        formatted_date = f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    elif len(digits) == 7:
        # 예: 2026215 -> 2026-02-15
        year = digits[:4]
        month = digits[4:5].zfill(2) if len(digits[4:]) == 3 else digits[4:6].zfill(2)
        day = digits[-2:].zfill(2)
        # 7자리는 모호하므로 안전하게 원본 유지 후 기호만 교체하는 방식 병행
        formatted_date = shoot_date.replace(' ', '').replace('.', '-').replace('/', '-')
    else:
        formatted_date = shoot_date.replace(' ', '').replace('.', '-').replace('/', '-')
    
    # 마지막으로 한 번 더 확인: 혹시라도 슬래시가 남아있으면 하이픈으로 변경 (Firestore 경로 오류 방지)
    formatted_date = formatted_date.replace('/', '-')
    
    payload = {
        'customerName': customer_name,
        'shootDate': formatted_date,
        'type': page_type,
        'originalUrl': original_url if page_type == 'original' else '',
        'retouchedUrl': original_url if page_type == 'retouched' else '',
        'videoUrl': '',
        'calendarUrl': ''
    }
    
    resp = requests.post(
        create_url,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        },
        json=payload,
        timeout=30
    )
    
    if resp.status_code != 200:
        raise Exception(f"페이지 생성 실패 ({resp.status_code}): {resp.text}")
    
    result = resp.json()
    download_url = result.get('downloadUrl', '')
    logger.info(f"다운로드 페이지 생성: {download_url}")
    return download_url

def update_sheet_cell(sheets_service, config, sheet_name, col, row_index, value):
    """시트의 특정 셀에 값 업데이트"""
    sheet_id = config['ledger_sheet_id']
    cell_range = f'{sheet_name}!{col}{row_index}'
    try:
        sheets_service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=cell_range,
            valueInputOption='USER_ENTERED',
            body={'values': [[value]]}
        ).execute()
        logger.info(f"시트 업데이트: {cell_range} ← {value[:30]}..." if len(str(value)) > 30 else f"시트 업데이트: {cell_range} ← {value}")
    except Exception as e:
        logger.error(f"시트 업데이트 실패: {cell_range}: {e}")

def _upload_and_create_page(bucket, config, customer_name, shoot_date, source_folder, page_type):
    """EXIF 검증 → ZIP 압축 → Firebase 업로드 → 다운로드 페이지 생성 (공통 로직)"""
    # 하위 폴더 포함 전체 JPG 카운트
    all_jpg = list(source_folder.rglob('*.jpg')) + list(source_folder.rglob('*.JPG'))
    all_jpg = [f for f in all_jpg if '@eaDir' not in str(f) and not f.name.startswith('.')]
    photo_count = len(all_jpg)
    if photo_count == 0:
        logger.warning(f"{customer_name}: JPG 파일 없음 → 스킵")
        return None

    # EXIF 촬영일 검증 (90% 기준)
    passed, total, matched = validate_exif_dates(source_folder, shoot_date, customer_name)
    if not passed:
        return None

    today_str = datetime.now(KST).strftime('%y%m%d')
    zip_name = f"스튜디오생일_{customer_name}_{today_str}.zip"
    zip_path = None
    try:
        zip_path = zip_folder(source_folder, zip_name)
        file_url = upload_to_firebase(bucket, zip_path, customer_name)
        download_url = create_download_page(config, customer_name, shoot_date, file_url, page_type=page_type)
        return download_url
    except Exception as e:
        logger.error(f"{customer_name}: 업로드/페이지 생성 실패: {e}")
        return None
    finally:
        if zip_path and zip_path.exists():
            zip_path.unlink()

# ============================================================
# 알림 기능
# ============================================================
def send_telegram_message(config, message):
    """텔레그램 봇을 통해 메시지 전송"""
    token = config.get('telegram_bot_token')
    chat_id = config.get('telegram_chat_id')
    if not token or not chat_id:
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML'}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code != 200:
            logger.error(f"텔레그램 발송 실패 ({resp.status_code}): {resp.text}")
    except Exception as e:
        logger.error(f"텔레그램 발송 중 오류: {e}")

def notify_delivery(config, customer_name, delivery_type, download_url):
    """발송 완료 알림 전송"""
    # 텔레그램 메시지 구성
    if 'premium' in delivery_type or 'retouched' in delivery_type or 'first' in delivery_type:
        grade = '프리미엄'
    else:
        grade = '베이직'
        
    if 'retouched' in delivery_type or 'second' in delivery_type:
        phase = '2차 (보정본)'
    else:
        phase = '1차 (원본)'
    
    msg = (
        f"<b>[스튜디오생일 발송 알림]</b>\n\n"
        f"📍 <b>고객명:</b> {customer_name}\n"
        f"📁 <b>분류:</b> {grade} ({phase})\n"
        f"🔗 <b>다운로드:</b> {download_url}\n"
        f"⚠️ <b>만료일:</b> 발송 후 7일 이내 (이후 자동 삭제)\n\n"
        f"시트 업데이트 및 업로드가 완료되었습니다."
    )
    
    send_telegram_message(config, msg)

def cleanup_firebase_storage(bucket, config):
    """설정된 기간(7일)이 지난 업로드 파일 자동 삭제"""
    retention_days = config.get('storage_retention_days', 7)
    logger.info(f"Firebase Storage 정리 시작 (보관 기간: {retention_days}일)...")
    
    count = 0
    now = datetime.now(timezone.utc)
    
    try:
        # auto/ 폴더 내 파일 리스팅
        blobs = bucket.list_blobs(prefix='auto/')
        for blob in blobs:
            # blob.time_created는 timezone-aware (UTC)
            age = now - blob.time_created
            if age.days >= retention_days:
                logger.info(f"[Storage 삭제] 오래된 파일 제거: {blob.name} (생성일: {blob.time_created})")
                blob.delete()
                count += 1
                
        if count > 0:
            logger.info(f"✅ Storage 정리 완료: {count}개 파일 삭제됨")
        else:
            logger.info("Storage 정리: 삭제할 오래된 파일 없음")
            
    except Exception as e:
        logger.error(f"Storage 정리 중 오류: {e}")
        notify_error(config, "Storage 정리", str(e))

def notify_error(config, component, error_detail):
    """장애 발생 시 알림 전송"""
    msg = (
        f"🚨 <b>[스튜디오생일 시스템 장애]</b>\n\n"
        f"📍 <b>위치:</b> {component}\n"
        f"❌ <b>내용:</b> {error_detail}\n\n"
        f"즉각적인 확인이 필요합니다."
    )
    send_telegram_message(config, msg)

# ============================================================
# Phase 2-A: 베이직 원본 발송
# ============================================================
def process_basic_deliveries():
    logger.info("베이직 원본 발송 처리 시작...")
    try:
        config = load_config()
        sheets_service = get_sheets_service()
    except Exception as e:
        logger.error(f"API 초기화 실패: {e}")
        return

    api_url = config.get('bdaystudio_api_url', '')
    api_key = config.get('bdaystudio_api_key', '')
    if not api_url or not api_key:
        logger.error("config.json에 bdaystudio_api_url 또는 bdaystudio_api_key가 없습니다")
        return

    try:
        bucket = init_firebase()
    except Exception as e:
        logger.error(f"Firebase 초기화 실패: {e}")
        return

    pending = get_pending_basic(sheets_service, config)
    if not pending:
        logger.info("베이직 발송 대기 건 없음")
        return

    for item in pending:
        customer_name = item['customer_name']
        phone = item['phone']
        shoot_date = item['shoot_date']
        row_index = item['row_index']

        logger.info(f"[베이직] 처리 중: {customer_name} ({phone})")

        source_folder = find_delivery_folder(customer_name, shoot_date, 'original')
        if not source_folder:
            logger.warning(f"[베이직] {customer_name}: 폴더 없음 → 스킵")
            continue

        download_url = _upload_and_create_page(bucket, config, customer_name, shoot_date, source_folder, 'original')
        if not download_url:
            continue

        update_sheet_cell(sheets_service, config, '베이직', 'E', row_index, download_url)
        
        # 알림 전송
        notify_delivery(config, customer_name, 'basic', download_url)
        
        logger.info(f"✅ [베이직] {customer_name} 완료! → {download_url}")
        logger.info(f"   카카오톡으로 위 링크를 전송하세요")

# ============================================================
# Phase 2-B: 프리미엄 1차/2차 발송
# ============================================================
def process_premium_deliveries():
    logger.info("프리미엄 발송 처리 시작...")
    try:
        config = load_config()
        sheets_service = get_sheets_service()
    except Exception as e:
        logger.error(f"API 초기화 실패: {e}")
        return

    api_url = config.get('bdaystudio_api_url', '')
    api_key = config.get('bdaystudio_api_key', '')
    if not api_url or not api_key:
        logger.error("config.json에 bdaystudio_api_url 또는 bdaystudio_api_key가 없습니다")
        return

    google_form_url = config.get('google_form_url', '')

    try:
        bucket = init_firebase()
    except Exception as e:
        logger.error(f"Firebase 초기화 실패: {e}")
        return

    first_pending, second_pending = get_pending_premium(sheets_service, config)

    # --- 1차 발송: 원본 + 구글폼 링크 ---
    for item in first_pending:
        customer_name = item['customer_name']
        phone = item['phone']
        shoot_date = item['shoot_date']
        row_index = item['row_index']

        logger.info(f"[프리미엄 1차] 처리 중: {customer_name} ({phone})")

        source_folder = find_delivery_folder(customer_name, shoot_date, 'original')
        if not source_folder:
            logger.warning(f"[프리미엄 1차] {customer_name}: 폴더 없음 → 스킵")
            continue

        download_url = _upload_and_create_page(bucket, config, customer_name, shoot_date, source_folder, 'original')
        if not download_url:
            continue

        update_sheet_cell(sheets_service, config, '프리미엄', 'E', row_index, download_url)

        # 알림 전송
        notify_delivery(config, customer_name, 'premium_first', download_url)

        logger.info(f"✅ [프리미엄 1차] {customer_name} 완료!")
        logger.info(f"   다운로드 링크: {download_url}")
        if google_form_url:
            logger.info(f"   구글폼 링크: {google_form_url}")
            logger.info(f"   카카오톡으로 위 두 링크를 함께 전송하세요")
        else:
            logger.info(f"   카카오톡으로 위 링크를 전송하세요")

    # --- 2차 발송: 보정본 ---
    for item in second_pending:
        customer_name = item['customer_name']
        phone = item['phone']
        shoot_date = item['shoot_date']
        row_index = item['row_index']

        logger.info(f"[프리미엄 2차] 처리 중: {customer_name} ({phone})")

        source_folder = find_delivery_folder(customer_name, shoot_date, 'retouched')
        if not source_folder:
            logger.warning(f"[프리미엄 2차] {customer_name}: 보정본 폴더 없음 → 스킵")
            continue

        download_url = _upload_and_create_page(bucket, config, customer_name, shoot_date, source_folder, 'retouched')
        if not download_url:
            continue

        update_sheet_cell(sheets_service, config, '프리미엄', 'H', row_index, download_url)
        
        # 알림 전송
        notify_delivery(config, customer_name, 'premium_retouched', download_url)
        
        logger.info(f"✅ [프리미엄 2차] {customer_name} 완료! → {download_url}")
        logger.info(f"   카카오톡으로 위 링크를 전송하세요")

# ============================================================
# Phase 0: 캘린더 → 시트 자동 등록
# ============================================================
def parse_calendar_event(event):
    """캘린더 이벤트에서 고객 정보 파싱
    제목 예: '사공*지 (2명) (프리미엄)'
    본문 예:
        예약 상품: 셀프촬영 예약
        네이버 예약자: 사공*지
        총 인원: 2명
        등급 및 옵션: (프리미엄)
    """
    summary = event.get('summary', '')
    description = event.get('description', '')
    start_str = event.get('start', {}).get('dateTime', '')
    start_time = parse_google_time(start_str)

    # 제목에서 파싱: "사공*지 (2명) (프리미엄)"
    name_match = re.match(r'^([^\(]+)', summary)
    customer_name = name_match.group(1).strip() if name_match else summary.strip()

    people_match = re.search(r'\((\d+)명\)', summary)
    num_people = people_match.group(1) if people_match else '1'

    if '프리미엄' in summary or 'premium' in summary.lower():
        grade = '프리미엄'
    elif '베이직' in summary or 'basic' in summary.lower():
        grade = '베이직'
    else:
        grade = '베이직'  # 등급 표시 없으면 베이직

    # description에서 보완 (제목에서 못 읽은 경우)
    if description:
        if not people_match:
            desc_people = re.search(r'총\s*인원\s*[:：]?\s*(\d+)명', description)
            if desc_people:
                num_people = desc_people.group(1)

        desc_grade = re.search(r'등급[^:：]*[:：]?\s*\(?(프리미엄|베이직)\)?', description)
        if desc_grade:
            grade = desc_grade.group(1)

    shoot_date = start_time.strftime('%Y. %-m. %-d') if start_time else ''
    reservation_time = start_time.strftime('%H:%M') if start_time else ''

    return {
        'customer_name': customer_name,
        'num_people': num_people,
        'grade': grade,
        'shoot_date': shoot_date,
        'reservation_time': reservation_time,
    }


def _get_sheet_rows(sheets_service, sheet_id, range_str):
    """시트에서 행 데이터 조회"""
    try:
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=sheet_id, range=range_str
        ).execute()
        return result.get('values', [])
    except Exception as e:
        logger.error(f"시트 조회 실패 ({range_str}): {e}")
        return []


def sync_calendar_to_sheets(calendar_service, sheets_service, config):
    """캘린더 이벤트를 시트에 자동 등록 (중복 시 스킵)"""
    logger.info("캘린더 → 시트 자동 등록 시작...")
    now = datetime.now(KST)
    time_min = (now - timedelta(hours=PAST_HOURS_LIMIT)).isoformat()
    time_max = (now + timedelta(hours=PAST_HOURS_LIMIT)).isoformat()

    try:
        events_result = calendar_service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=time_min, timeMax=time_max,
            singleEvents=True, orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])
    except Exception as e:
        logger.error(f"캘린더 조회 실패 (시트 등록): {e}")
        return

    if not events:
        logger.info("시트 등록: 예약 이벤트 없음")
        return

    sheet_id = config['ledger_sheet_id']

    # 기존 시트 데이터 로드
    basic_rows = _get_sheet_rows(sheets_service, sheet_id, BASIC_SHEET_RANGE)
    premium_rows = _get_sheet_rows(sheets_service, sheet_id, PREMIUM_SHEET_RANGE)

    registered_count = 0
    skipped_count = 0

    for event in events:
        info = parse_calendar_event(event)
        if not info['customer_name']:
            continue

        target_sheet = '프리미엄' if info['grade'] == '프리미엄' else '베이직'
        existing_rows = premium_rows if info['grade'] == '프리미엄' else basic_rows

        # 중복 확인 (촬영일 + 고객명)
        normalized_shoot = normalize_date(info['shoot_date'])
        already_exists = False
        for row in existing_rows:
            row_date = normalize_date(row[0]) if len(row) > 0 else ''
            row_name = row[1].strip() if len(row) > 1 else ''
            if row_date == normalized_shoot and is_name_match(info['customer_name'], row_name):
                already_exists = True
                break

        if already_exists:
            logger.info(f"[시트 등록] {info['customer_name']}: 이미 {target_sheet} 시트에 존재 → 스킵")
            skipped_count += 1
            continue

        # 새 행 추가 (전화번호 칸은 비워둠)
        if target_sheet == '베이직':
            # A:촬영일, B:고객이름, C:전화번호, D:리뷰확인, E:원본발송, F:비고
            new_row = [info['shoot_date'], info['customer_name'], '', '', '', f"{info['num_people']}명"]
            append_range = '베이직!A:F'
        else:
            # A:촬영일, B:고객이름, C:전화번호, D:주소, E~I:발송관련, J:비고
            new_row = [info['shoot_date'], info['customer_name'], '', '', '', '', '', '', '', f"{info['num_people']}명"]
            append_range = '프리미엄!A:J'

        try:
            sheets_service.spreadsheets().values().append(
                spreadsheetId=sheet_id,
                range=append_range,
                valueInputOption='USER_ENTERED',
                insertDataOption='INSERT_ROWS',
                body={'values': [new_row]}
            ).execute()
            logger.info(f"✅ [시트 등록] {info['customer_name']} ({info['grade']}, {info['num_people']}명) → {target_sheet} 시트에 추가 완료")
            registered_count += 1

            # 로컬 캐시에도 추가 (동일 실행 중 중복 방지)
            existing_rows.append(new_row)
        except Exception as e:
            logger.error(f"[시트 등록] {info['customer_name']}: 행 추가 실패: {e}")

    logger.info(f"시트 등록 완료: 신규 {registered_count}건, 스킵 {skipped_count}건")


# ============================================================
# 메인
# ============================================================
def main():
    logger.info("=" * 60)
    logger.info("스튜디오생일 자동화 v6.0 시작 (캘린더→시트 등록 + 원본/내보내기 + 베이직/프리미엄 발송)")
    logger.info(f"설정: 과거 {PAST_HOURS_LIMIT}시간 예약 처리, 버퍼 ±{TIME_BUFFER_MINUTES}분")

    # [v6.0] 중복 실행 방지 (File Lock)
    if LOCK_FILE.exists():
        # 파일이 있지만 프로세스가 죽었을 수도 있으므로 생성 시간 체크 (선택 사항)
        # 여기서는 단순하게 이미 실행 중이라고 판단하고 종료
        logger.warning(f"⚠️ 이미 다른 인스턴스가 실행 중입니다. (Lock 파일 발견: {LOCK_FILE})")
        return

    try:
        # Lock 파일 생성
        with open(LOCK_FILE, 'w') as f:
            f.write(str(os.getpid()))
        
        try:
            service = None
            try:
                service = get_calendar_service()
                processed_events = process_appointments(service)
            except Exception as e:
                logger.error(f"예약 처리 중 오류: {e}")

            # 캘린더 → 시트 자동 등록
            try:
                sheets_svc = get_sheets_service()
                config = load_config()
                if service:
                    sync_calendar_to_sheets(service, sheets_svc, config)
                else:
                    logger.warning("Calendar 서비스 없음 → 시트 자동 등록 스킵")
            except Exception as e:
                logger.error(f"시트 자동 등록 중 오류: {e}")

            try:
                process_basic_deliveries()
            except Exception as e:
                logger.error(f"베이직 발송 처리 중 오류: {e}")

            try:
                process_premium_deliveries()
            except Exception as e:
                logger.error(f"프리미엄 발송 처리 중 오류: {e}")

            # Firebase Storage 정리 (v5.9 추가)
            try:
                bucket = init_firebase()
                cleanup_firebase_storage(bucket, config)
            except Exception as e:
                logger.error(f"Storage 정리 준비 중 오류: {e}")

            logger.info("전체 자동화 완료!")
        except Exception as e:
            logger.error(f"메인 루틴 실행 중 치명적 오류: {e}")
            try:
                config = load_config()
                notify_error(config, "메인 시스템", str(e))
            except:
                pass
    finally:
        # Lock 파일 제거
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
        
    logger.info("=" * 60)

if __name__ == '__main__':
    main()
