# OAuth 토큰 복구 계획

구글 시트 인증 토큰(`drive_token.pickle`)이 만료/취소되어 자동화가 중단되었습니다. 이를 해결하기 위해 새로운 토큰을 생성하고 NAS에 적용합니다.

## 해결 방법

1.  **로컬(Mac)에서 토큰 재발행**: 브라우저를 띄울 수 있는 현재 환경에서 인증을 진행합니다.
2.  **NAS로 전송**: 새로 생성된 `drive_token.pickle`을 NAS의 설정 폴더로 복사합니다.

## Proposed Changes

### 1. 토큰 생성 스크립트 작성

#### [NEW] [generate_drive_token.py](file:///Users/jinito/Workspaces/Opencode/studiobday-automation/generate_drive_token.py)

```python
import pickle
import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

def main():
    creds = None
    # 로컬에서 실행 시 oauth_credentials.json 파일이 필요합니다.
    # NAS에 있는 파일을 로컬로 가져와서 실행해야 합니다.
    client_secrets = 'oauth_credentials.json'
    
    if not os.path.exists(client_secrets):
        print(f"Error: {client_secrets} 파일이 없습니다. NAS에서 가져오세요.")
        return

    flow = InstalledAppFlow.from_client_secrets_file(client_secrets, SCOPES)
    creds = flow.run_local_server(port=0)
    
    with open('drive_token.pickle', 'wb') as token:
        pickle.dump(creds, token)
    print("✅ drive_token.pickle 생성이 완료되었습니다!")

if __name__ == '__main__':
    main()
```

## 실행 안내 (사용자 조치 필요)

1.  **NAS에서 파일 가져오기**: NAS의 `~/studio_automation/scripts/oauth_credentials.json`을 현재 Mac 폴더로 가져옵니다.
2.  **스크립트 실행**: Mac 터미널에서 `python3 generate_drive_token.py`를 실행합니다.
3.  **인증**: 브라우저가 열리면 `bdayyatap@gmail.com` 계정으로 로그인하고 권한을 승인합니다.
4.  **NAS로 전송**: 생성된 `drive_token.pickle`을 NAS의 `~/studio_automation/scripts/` 폴더에 덮어씁니다.
