# Narwal 토큰 구하는 방법

> 토큰은 계정 비밀번호와 똑같이 취급하세요. 본인 계정과 기기에서만 진행하고,
> 작업 후 캡처 파일·프록시 인증서·클립보드 기록을 삭제하세요.

통합 추가 화면에서 **나르왈 계정으로 로그인**하는 방식을 권장합니다. 이 문서는
계정 로그인이 지원되지 않는 지역이나 기존 토큰 방식을 계속 사용할 때만 필요합니다.

가장 권장하는 방법은 개인정보가 없는 **새 Android 에뮬레이터**에 공식 Narwal Freo
앱을 설치하는 것입니다. 작업이 끝나면 에뮬레이터 전체를 삭제할 수 있어 실제 휴대전화의
보안 설정을 건드릴 필요가 없습니다.

~~설정이 너무 복잡하면 Codex한테 시키면 토큰 파일까지 뽑아줍니다. 네, 그렇게 만들었습니다.~~

## 준비물

- 개인정보가 없는 Android 에뮬레이터 또는 테스트용 기기
- 공식 Narwal Freo 앱
- HTTP Toolkit 또는 mitmproxy 같은 로컬 HTTPS 디버깅 프록시

공식 앱은 TLS 인증서 고정을 사용할 수 있습니다. 필요한 CA 인증서 설치나 SSL 고정
해제는 폐기 가능한 테스트 환경에서만 하세요. 평소 사용하는 휴대전화의 보안을
약화시키지 마세요.

## 절차

1. PC에서 디버깅 프록시를 실행하고 Android 테스트 기기를 연결합니다.
2. 테스트 기기에 프록시 CA 인증서를 설치합니다.
3. Narwal 앱을 열고 본인 계정으로 로그인합니다.
4. 앱을 완전히 종료한 뒤 다시 열어 토큰 갱신 요청을 발생시킵니다.
5. 프록시에서 `/user-authentication-server/v1/token/refresh` 요청을 찾습니다.
6. JSON 응답의 `result` 객체에서 다음 값을 복사합니다.
   - `token` → **Narwal 액세스 토큰**
   - `refreshToken` → **Narwal 갱신 토큰**
7. Home Assistant의 Narwal Cloud 추가 화면에서 **앱 토큰 직접 입력**을 선택해
   두 값을 입력합니다.
8. 프록시를 종료하고 저장된 응답, 인증서, 클립보드 기록을 삭제합니다.

---

# How to obtain Narwal tokens

> Treat tokens like your account password. Use only your own account and
> devices. Delete captures, proxy certificates, and clipboard history after
> finishing.

The recommended setup is **Sign in with a Narwal account** in the integration
flow. Use this guide only for regions where account login is unavailable or
when retaining an existing token-based setup.

Use a fresh **Android emulator with no personal data**. After extraction, the
whole emulator and its proxy certificate can be deleted without weakening the
security of your everyday phone.

~~If this looks like too much work, ask Codex. It will even export the token file for you. Yes, that is how this was built.~~

1. Run an HTTPS debugging proxy such as HTTP Toolkit or mitmproxy.
2. Connect a disposable Android emulator and install the proxy CA certificate.
3. Install the official Narwal Freo app and sign in to your own account.
4. Fully close and reopen the app to trigger token refresh.
5. Locate `/user-authentication-server/v1/token/refresh` in the proxy.
6. Copy `result.token` and `result.refreshToken` from the JSON response.
7. Select **Enter app tokens manually** in the Home Assistant integration and
   enter both values.
8. Stop the proxy and delete all captured responses and certificates.

Use CA trust or SSL-unpinning only inside the disposable test environment.
