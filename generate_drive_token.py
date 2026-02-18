import pickle
import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# 전용 스코프 설정
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

def main():
    creds = None
    client_secrets = 'oauth_credentials.json'
    
    if not os.path.exists(client_secrets):
        print(f"❌ Error: {client_secrets} 파일이 없습니다. NAS에서 가져온 파일이 이 폴더에 있어야 합니다.")
        return

    print("🚀 구글 인증을 시작합니다. 브라우저가 열리면 로그인해 주세요.")
    flow = InstalledAppFlow.from_client_secrets_file(client_secrets, SCOPES)
    creds = flow.run_local_server(port=0)
    
    with open('drive_token.pickle', 'wb') as token:
        pickle.dump(creds, token)
    print("✅ drive_token.pickle 생성이 완료되었습니다!")
    print("👉 이제 이 파일을 NAS의 ~/studio_automation/scripts/ 폴더에 덮어씌워 주세요.")

if __name__ == '__main__':
    main()
