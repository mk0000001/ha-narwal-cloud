# Home Assistant용 Narwal Cloud

Narwal 글로벌/한국 클라우드를 사용하는 비공식 Home Assistant 통합입니다.
Narwal Freo YJCC012에서 개발하고 검증했습니다.

## 주요 기능

- 배터리, 이동 상태, 청소 모드, 터보 모드 및 표준 로봇청소기 상태
- 일시정지, 재개, 중지, 충전대 복귀
- 드리미 호환 실시간 맵/맵 데이터, 현재 위치, 방 자동 인식 및 구역 청소
- Freo Mind, 진공, 물걸레, 진공+물걸레, 진공 후 물걸레 모드
- 흡입력, 물걸레 습도, 청소 횟수 설정
- 물걸레 세척·건조 시작 및 종료
- 필터, 물걸레, 사이드 브러시, 스펀지, 메인 브러시 소모율
- 액세스 토큰 자동 갱신

## HACS 설치

1. HACS에서 우측 상단 메뉴를 열고 **사용자 지정 저장소**를 선택합니다.
2. 저장소에 `https://github.com/mk0000001/ha-narwal-cloud`를 입력합니다.
3. 유형으로 **Integration**을 선택하고 추가합니다.
4. HACS에서 **Narwal Cloud**를 찾아 설치합니다.
5. Home Assistant를 재시작합니다.
6. **설정 → 기기 및 서비스 → 통합 구성 요소 추가**에서
   **Narwal Cloud (unofficial)**를 선택합니다.
7. Narwal 앱에서 얻은 **액세스 토큰**과 **갱신 토큰**을 입력합니다.

수동 설치 시 `custom_components/narwal_cloud` 폴더를 Home Assistant의
`custom_components` 아래에 복사하고 재시작하면 됩니다.

토큰 발급 절차는 [토큰 구하는 방법 / How to obtain tokens](docs/token_setup.md)을
참고하세요. 입력란은 비밀번호 형식으로 가려지며 토큰은 Home Assistant의
config entry에만 저장됩니다.

## 보안 및 주의사항

토큰은 Narwal 계정을 제어할 수 있는 비밀번호와 같습니다. GitHub 이슈,
스크린샷 또는 로그에 토큰을 올리지 마세요. 이 저장소에는 계정·기기 ID,
토큰, 인증서 및 비공개 캡처가 포함되어 있지 않습니다.

이 프로젝트는 Narwal과 관련 없는 비공식 통합입니다. 클라우드 프로토콜은
공개 문서가 없으며 언제든 변경될 수 있습니다. 현재 검증 모델은 YJCC012입니다.

---

# Narwal Cloud for Home Assistant

An unofficial Home Assistant integration for Narwal robot vacuums using the
global/Korean Narwal cloud. Developed and verified with the Narwal Freo
YJCC012.

## Features

- Battery, movement, cleaning, turbo, and standard vacuum states
- Pause, resume, stop, and return-to-dock
- Dreame-compatible live map/map data, position, rooms, and segment cleaning
- Freo Mind, vacuum, mop, vacuum-and-mop, and vacuum-then-mop modes
- Suction, mop humidity, and cleaning-cycle controls
- Mop washing/drying start and finish controls
- Consumable remaining time and percentage
- Automatic access-token refresh

## HACS installation

1. Open the HACS menu and select **Custom repositories**.
2. Add `https://github.com/mk0000001/ha-narwal-cloud` as an **Integration**.
3. Find and install **Narwal Cloud**, then restart Home Assistant.
4. Add **Narwal Cloud (unofficial)** from **Settings → Devices & services**.
5. Enter the Narwal app **access token** and **refresh token**.

For manual installation, copy `custom_components/narwal_cloud` into the
matching Home Assistant directory and restart.

Guide: [토큰 구하는 방법 / How to obtain tokens](docs/token_setup.md)

The fields are masked as passwords. Tokens are stored only in the Home
Assistant config entry and are not written to integration logs.

## Disclaimer

This project is not affiliated with Narwal. The cloud protocol is undocumented
and may change. YJCC012 is the currently verified model.

## License

MIT
