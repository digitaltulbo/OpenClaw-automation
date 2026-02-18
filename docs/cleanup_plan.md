# Firebase Storage 자동 정리 시스템 구축 계획

Firebase Storage의 용량 제한(5GB 무료 등)을 효율적으로 관리하고 비용을 절감하기 위해, 고객에게 링크를 발송한 지 7일이 지난 파일을 자동으로 삭제하는 기능을 추가합니다.

## Proposed Changes

### [Component] auto_organizer_console.py

#### [MODIFY] [auto_organizer_console.py](file:///Users/jinito/Workspaces/Opencode/studiobday-automation/auto_organizer_console.py)

- **`cleanup_firebase_storage(bucket, days=7)` 함수 추가**: 
  - Firebase Storage의 `deliveries/` 또는 `auto/` 경로 내의 모든 파일을 리스팅합니다.
  - 파일의 생성 시간(`time_created`)을 확인하여 현재 시간 기준 7일(또는 설정값)이 지난 파일을 삭제합니다.
  - 삭제된 파일 목록을 로그에 기록합니다.
- **`main()` 함수 통합**:
  - 스크립트 실행 마지막 단계에서 이 청소 함수를 호출하도록 통합합니다.
- **`config.json` 연동**: 
  - `storage_retention_days` 설정을 추가하여 삭제 주기를 관리자가 직접 조절할 수 있게 합니다 (기본값 7일).

## Verification Plan

### Automated Tests
- 삭제 주기를 0일로 설정하여 방금 업로드한 파일이 즉시 삭제되는지 테스트합니다.
- 7일 이상 된 테스트 파일을 생성하여 실제 삭제 로직이 작동하는지 확인합니다.

### Manual Verification
- 실행 로그 (`auto_organizer.log`)에 `[Storage 정리] 00개 파일 삭제 완료` 메시지가 남는지 확인합니다.
