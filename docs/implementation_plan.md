# 구글 캘린더 → 구글 시트 자동 등록 기능 추가

캘린더 이벤트를 읽어 구글 시트에 고객 행이 없으면 자동 등록하는 기능을 `auto_organizer_console.py`에 추가한다.

## 현재 코드 분석 요약

| 항목 | 현재 상태 |
|------|----------|
| **인증** | Calendar: `credentials.json` (서비스 계정), Sheets: `drive_token.pickle` (OAuth) |
| **Config** | `~/studio_automation/scripts/config.json` → `ledger_sheet_id` 키 사용 |
| **베이직 시트** | `베이직!A2:F100` — A:촬영일, B:고객이름, C:전화번호, D:리뷰확인, E:원본발송, F:비고 |
| **프리미엄 시트** | `프리미엄!A2:J100` — A:촬영일, B:고객이름, C:전화번호, D:주소, E:1차발송, F:보정요청일, G:보정완료, H:2차발송, I:최종컨펌일, J:비고 |
| **캘린더** | `bdayyatap@gmail.com`, 이벤트 제목 예: `사공*지 (2명) (프리미엄)` |
| **main() 흐름** | `process_appointments()` → `process_basic_deliveries()` → `process_premium_deliveries()` |

## Proposed Changes

### Calendar Event Parser

#### [MODIFY] [auto_organizer_console.py](file:///Users/jinito/Workspaces/Opencode/studiobday-automation/auto_organizer_console.py)

**새 함수 추가:**

1. `parse_calendar_event(event)` — 이벤트 제목+본문에서 정보 추출:
   - 이벤트 제목에서 고객명(마스킹된 이름), 인원수, 등급 파싱
   - 이벤트 본문(description)에서도 동일 정보 보완 추출
   - 반환: `{'customer_name': str, 'num_people': str, 'grade': str, 'shoot_date': str, 'reservation_time': str}`

```python
def parse_calendar_event(event):
    """캘린더 이벤트에서 고객 정보 파싱"""
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
        grade = '베이직'  # 등급 없으면 베이직
    
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
```

2. `sync_calendar_to_sheets(calendar_service, sheets_service, config)` — 메인 동기화 함수:
   - 오늘(과거 6시간~) 캘린더 이벤트 조회
   - 해당 등급 시트에서 기존 고객 확인 (촬영일+고객명 기준)
   - 없으면 새 행 추가 (전화번호 칸 비워둠)
   - 있으면 스킵

```python
def sync_calendar_to_sheets(calendar_service, sheets_service, config):
    """캘린더 이벤트를 시트에 자동 등록"""
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
        
        # 새 행 추가
        if target_sheet == '베이직':
            new_row = [info['shoot_date'], info['customer_name'], '', '', '', f"{info['num_people']}명"]
            append_range = '베이직!A:F'
        else:
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
```

3. `_get_sheet_rows(sheets_service, sheet_id, range_str)` — 시트 행 조회 헬퍼

**main() 함수 수정:**

`process_appointments()` 호출 직후, 발송 처리 전에 `sync_calendar_to_sheets()` 호출 추가:

```diff
 def main():
     ...
     try:
         service = get_calendar_service()
         processed_events = process_appointments(service)
     except Exception as e:
         logger.error(f"예약 처리 중 오류: {e}")
 
+    # 캘린더 → 시트 자동 등록
+    try:
+        sheets_service = get_sheets_service()
+        config = load_config()
+        sync_calendar_to_sheets(service, sheets_service, config)
+    except Exception as e:
+        logger.error(f"시트 자동 등록 중 오류: {e}")
+
     try:
         process_basic_deliveries()
     ...
```

### Folder Selection Refinement

#### [MODIFY] [auto_organizer_console.py](file:///Users/jinito/Workspaces/Opencode/studiobday-automation/auto_organizer_console.py)

`find_delivery_folder` 함수를 수정하여 발송 단계에 따라 `내보내기` 또는 `보정본` 폴더를 우선적으로 찾도록 한다.

```python
def find_delivery_folder(customer_name, shoot_date=None, delivery_type='original'):
    """발송용 폴더 탐색: delivery_type 에 따라 '내보내기' 또는 '보정본' 우선 탐색"""
    normalized_shoot = normalize_date(shoot_date) if shoot_date else ''
    
    # 1순위: Console 폴더 (주로 베이직/프리미엄 1차 원본)
    # 2순위: 프리미엄 작업 폴더 (주로 프리미엄 2차 보정본)
    search_paths = [CLIENTS_FOLDER, PREMIUM_FOLDER]
    
    for base_folder in search_paths:
        if not base_folder.exists(): continue
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
```

**호출 부 수정:**
- `process_basic_deliveries()`: `find_delivery_folder(customer_name, shoot_date, 'original')`
- `process_premium_deliveries()` 1차: `find_delivery_folder(customer_name, shoot_date, 'original')`
- `process_premium_deliveries()` 2차: `find_delivery_folder(customer_name, shoot_date, 'retouched')`

## Verification Plan

### Automated Tests

원격 Synology NAS 환경에서 실행해야 하므로 자동 테스트는 불가.

### Manual Verification

사용자가 아래 명령으로 직접 테스트:

```bash
cd /var/services/homes/jin/studio_automation/scripts && \
/var/services/homes/jin/studio_automation/venv/bin/python auto_organizer_console.py
```

**확인 사항:**
1. 로그에 `[시트 등록]` 메시지가 나타나는지 확인
2. 오늘 프리미엄 4팀(김수용, 홍원철, 사공희지, 이혜인)이 프리미엄 시트에 등록되는지 확인
3. 이미 있는 고객은 "이미 ... 시트에 존재 → 스킵" 로그가 나오는지 확인
4. 전화번호가 비어있는 고객에 대해 "전화번호 미입력 → 발송 대기" 로그가 나오는지 확인
5. 기존 발송 로직이 정상 동작하는지 확인

> [!IMPORTANT]
> 이 스크립트는 Synology NAS에서 실행됩니다. 로컬 Mac에서는 테스트 불가하며, 수정된 파일을 NAS에 복사한 후 테스트해야 합니다.
