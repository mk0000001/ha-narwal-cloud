# Narwal 토큰 구하는 방법

> 토큰은 계정 비밀번호와 동일하게 취급하세요. 반드시 본인 계정과 본인
> 기기에서만 진행하고, 완료 후 캡처 파일과 프록시 인증서를 삭제하세요.

Narwal은 제3자용 공개 OAuth 로그인을 제공하지 않으므로 현재 통합은 공식
앱이 발급한 토큰 두 개를 사용합니다.

가장 권장하는 방법은 개인 정보가 전혀 없는 **새 Android 에뮬레이터를
설치해서 작업하는 것**입니다. 토큰을 얻은 뒤 에뮬레이터와 프록시 인증서를
통째로 삭제할 수 있어 실제 휴대전화의 보안 설정을 건드리지 않아도 됩니다.

~~설정이 너무 복잡하면 Codex한테 시키면 토큰 파일까지 알아서 빼준다고
합니다. 실화입니다.~~

## 준비

- 개인 정보가 없는 테스트용 Android 에뮬레이터 또는 여분의 Android 기기
- 공식 Narwal Freo 앱
- HTTPS 트래픽을 확인할 수 있는 로컬 디버깅 프록시
  (예: HTTP Toolkit 또는 mitmproxy)

공식 앱은 TLS 인증서 고정을 사용할 수 있습니다. 이 경우 테스트용
에뮬레이터에서만 사용자 CA 신뢰 설정 또는 SSL 고정 해제가 필요합니다.
일상적으로 사용하는 휴대전화의 보안을 낮추지 마세요.

## 절차

1. 디버깅 프록시를 내 PC에서 실행하고 Android 테스트 기기를 연결합니다.
2. 테스트 기기에 프록시 CA 인증서를 설치합니다.
3. Narwal 앱을 열고 본인 Google/Narwal 계정으로 로그인합니다.
4. 앱을 완전히 종료한 뒤 다시 열어 토큰 갱신 요청을 발생시킵니다.
5. 프록시에서 다음 요청을 찾습니다.

   `/user-authentication-server/v1/token/refresh`

6. JSON 응답의 `result` 안에서 다음 두 값을 복사합니다.

   - `token` → Home Assistant의 **Narwal 액세스 토큰**
   - `refreshToken` → Home Assistant의 **Narwal 갱신 토큰**

7. Home Assistant에서 **Narwal Cloud (unofficial)** 통합을 추가하고 두
   값을 입력합니다.
8. 프록시를 종료하고 저장된 응답, 인증서, 클립보드 기록을 삭제합니다.

토큰이 만료되면 통합이 갱신 토큰으로 새 토큰을 자동 저장합니다. 갱신
토큰까지 만료되거나 로그아웃으로 폐기된 경우 위 절차를 다시 진행하세요.

---

# How to obtain Narwal tokens

> Treat tokens like your account password. Use only your own account and
> devices. Delete captures and proxy certificates after finishing.

Narwal does not currently provide a public third-party OAuth flow. This
integration therefore uses the two tokens issued to the official app.

The recommended approach is to install a **fresh Android emulator containing
no personal data**. After obtaining the tokens, you can delete the whole
emulator and proxy certificate without weakening your everyday phone.

~~If this looks like too much work, ask Codex. Apparently it will even export
the token file for you. True story.~~

## Requirements

- A clean Android emulator or spare Android test device
- The official Narwal Freo app
- A local HTTPS debugging proxy such as HTTP Toolkit or mitmproxy

The app may use TLS certificate pinning. If so, use CA trust or SSL-unpinning
only inside the disposable test environment. Do not weaken the security of
your everyday phone.

## Steps

1. Run the debugging proxy on your computer and connect the Android test
   device.
2. Install the proxy CA certificate on the test device.
3. Open the Narwal app and sign in to your own Google/Narwal account.
4. Fully close and reopen the app to trigger token refresh.
5. Find this request in the proxy:

   `/user-authentication-server/v1/token/refresh`

6. Copy these fields from the JSON response `result` object:

   - `token` → **Narwal access token**
   - `refreshToken` → **Narwal refresh token**

7. Add **Narwal Cloud (unofficial)** in Home Assistant and enter both values.
8. Stop the proxy and delete saved responses, certificates, and clipboard
   history.

The integration automatically rotates the access token. Repeat these steps
only if the refresh token is expired or revoked.
