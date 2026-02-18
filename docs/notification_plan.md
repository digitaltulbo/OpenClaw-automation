# 알림 기능 추가 (텔레그램/이메일)

링크 생성 및 시트 업데이트 완료 시 관리자에게 알림을 보내는 기능을 추가한다.

## 현재 상태 분석

- **이메일**: `config.json`에 `gmail_sender`와 `gmail_app_password`가 이미 설정되어 있음.
- **텔레그램**: 추가 설정(Token, Chat ID)이 필요함.

## Proposed Changes

### 1. 알림 유틸리티 함수 추가

#### [MODIFY] [auto_organizer_console.py](file:///Users/jinito/Workspaces/Opencode/studiobday-automation/auto_organizer_console.py)

**새 함수 추가:**

```python
def send_telegram_message(config, message):
    """텔레그램 봇을 통해 메시지 전송"""
    token = config.get('telegram_bot_token')
    chat_id = config.get('telegram_chat_id')
    if not token or not chat_id:
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML'}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        logger.error(f"텔레그램 발송 실패: {e}")

def send_email_notification(config, subject, body):
    """Gmail SMTP를 통해 이메일 알림 전송"""
    import smtplib
    from email.mime.text import MIMEText
    
    sender = config.get('gmail_sender')
    password = config.get('gmail_app_password')
    if not sender or not password:
        return

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = sender  # 나에게 보내기

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender, password)
            server.send_message(msg)
    except Exception as e:
        logger.error(f"이메일 발송 실패: {e}")

def notify_delivery(config, customer_name, delivery_type, download_url):
    """통합 알림 전송 (텔레그램 우선, 없으면 이메일)"""
    grade = '프리미엄' if 'premium' in delivery_type or 'retouched' in delivery_type or 'first' in delivery_type else '베이직'
    phase = '2차(보정본)' if 'retouched' in delivery_type or 'second' in delivery_type else '1차(원본)'
    
    subject = f"[{grade}] {customer_name}님 {phase} 발송 완료"
    body = (
        f"<b>[스튜디오생일 알림]</b>\n\n"
        f"고객명: {customer_name}\n"
        f"분류: {grade} ({phase})\n"
        f"다운로드 페이지: {download_url}\n\n"
        f"시트 업데이트 및 업로드가 완료되었습니다."
    )
    
    # 텔레그램 발송 시도
    if config.get('telegram_bot_token'):
        send_telegram_message(config, body)
    
    # 이메일 발송 시도 (항상 또는 백업으로 설정 가능)
    send_email_notification(config, subject, body.replace('<b>', '').replace('</b>', ''))
```

### 2. 발송 로직에 알림 호출 추가

- `process_basic_deliveries()`와 `process_premium_deliveries()` 완료 시점에 `notify_delivery()` 호출 추가.

### 3. Config 추가 요청

텔레그램 알림을 위해 `config.json`에 다음 항목 추가가 필요함:
- `telegram_bot_token`
- `telegram_chat_id`

## Verification Plan

### Manual Verification

1. `config.json`에 테스트용 텔레그램 정보 입력.
2. 스크립트 수동 실행하여 실제 알림이 오는지 확인.
