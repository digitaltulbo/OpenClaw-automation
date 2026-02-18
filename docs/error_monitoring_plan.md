# Error Monitoring 및 Notification 시스템 구축 계획

자동화 스크립트 실행 중 발생하는 치명적인 오류(인증 만료, API 서버 장애 등)를 실시간으로 파악하기 위해 텔레그램 알림 기능을 강화합니다.

## User Review Required

> [!IMPORTANT]
> 매 실행마다 발생하는 사소한 경고(폴더 없음 등)는 제외하고, **시스템 중단이 우려되는 치명적 오류** 위주로 알림을 보냅니다. 알림이 너무 많아지는 것을 방지하기 위함입니다.

## Proposed Changes

### [Component] auto_organizer_console.py

#### [MODIFY] [auto_organizer_console.py](file:///Users/jinito/Workspaces/Opencode/studiobday-automation/auto_organizer_console.py)

- **`notify_error` 함수 추가**: 에러 발생 시 🚨 이모지와 함께 상세 내용을 텔레그램으로 전송하는 전용 함수를 구현합니다.
- **Top-level Error Catching**: `main()` 함수 전체를 `try-except`로 감싸 예상치 못한 크래시 발생 시 즉시 알림을 보냅니다.
- **인증(OAuth) 감시**: `get_oauth_credentials`에서 토큰이 유효하지 않을 경우 즉시 알림을 보내 "맥미니에서 조치 필요" 메시지를 전달합니다.
- **주요 API 장애 감시**: Google Sheets, Firebase, bdaystudio API 호출 실패 시 알림을 추가합니다.

## Verification Plan

### Automated Tests
- 의도적으로 `config.json`의 API 키를 틀리게 설정하거나 토큰 파일을 삭제하여 텔레그램으로 에러 메시지가 잘 오는지 확인합니다.
- `python3 auto_organizer_console.py` 수동 실행을 통해 로그와 텔레그램 메시지 일치 여부를 검증합니다.
