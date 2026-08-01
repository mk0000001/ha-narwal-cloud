# Home Assistant용 Narwal Cloud

한국/글로벌 Narwal Cloud를 사용하는 비공식 Home Assistant 통합입니다. Narwal Freo
YJCC012에서 개발하고 검증했습니다.

## 주요 기능

- 나르왈 계정 로그인과 액세스/갱신 토큰 자동 교체
- 기존 사용자를 위한 앱 토큰 직접 입력 방식
- 배터리, 이동 상태, 청소 상태, 터보 모드
- 시작, 일시 정지, 재개, 중지, 충전대로 복귀
- 실시간 지도 데이터, 현재 위치, 방 목록, 구역별 청소
- Freo Mind, 진공, 물걸레, 진공+물걸레, 진공 후 물걸레 모드
- 흡입력, 물걸레 습도, 청소 횟수 설정
- 물걸레 세척/건조 시작과 종료
- 필터, 물걸레, 사이드 브러시, 스펀지, 메인 브러시 소모품 시간
- 기본 1초 상태 갱신과 1~300초 사용자 지정 폴링 주기

## HACS 설치

1. HACS 우측 상단 메뉴에서 **사용자 지정 저장소**를 선택합니다.
2. `https://github.com/mk0000001/ha-narwal-cloud`를 **Integration** 유형으로 추가합니다.
3. **Narwal Cloud**를 설치하고 Home Assistant를 다시 시작합니다.
4. **설정 → 기기 및 서비스 → 통합 구성 요소 추가**에서
   **Narwal Cloud (unofficial)**를 선택합니다.
5. 권장 방식인 **나르왈 계정으로 로그인**을 선택하고 앱 계정을 입력합니다.

기존에 토큰으로 설치한 항목은 통합 항목의 **재구성**을 눌러 계정 자동 로그인으로
전환할 수 있습니다. 토큰 방식이 필요한 경우 [토큰 구하는 방법](docs/token_setup.md)을
참고하세요.

통합 항목의 **구성**에서 상태 갱신 주기를 1~300초로 변경할 수 있습니다. 기본값은
1초이며 클라우드 또는 네트워크 사용량을 줄이려면 값을 늘리세요.

## 계정과 보안

이메일과 비밀번호는 Home Assistant의 로컬 구성 항목에만 저장됩니다. 통합 소스,
GitHub, 진단 정보 및 로그에는 기록하지 않습니다. Home Assistant 호스트와 백업에
접근할 수 있는 사람은 로컬 비밀 정보에도 접근할 수 있으므로 호스트와 백업을
보호하세요.

로봇을 다른 계정에서 사용할 때는 로봇을 초기화하거나 소유권을 이전하지 말고,
나르왈 앱의 메인 계정에서 해당 사용자를 초대해 공유하세요.

이 프로젝트는 Narwal과 관계없는 비공식 통합입니다. 비공개 클라우드 프로토콜은
예고 없이 변경될 수 있습니다.

---

# Narwal Cloud for Home Assistant

An unofficial Home Assistant integration for the Korean/global Narwal Cloud,
developed and verified with the Narwal Freo YJCC012.

## Features

- Narwal account login with automatic access/refresh-token rotation
- Manual app-token fallback for existing users
- Battery, movement, cleaning, and turbo state
- Start, pause, resume, stop, and return-to-dock
- Live map data, robot position, rooms, and segment cleaning
- Freo Mind, vacuum, mop, vacuum-and-mop, and vacuum-then-mop modes
- Suction, mop humidity, and cleaning-cycle controls
- Mop washing/drying start and finish controls
- Consumable remaining-time sensors
- One-second default polling, configurable from 1 to 300 seconds

## Installation

Add `https://github.com/mk0000001/ha-narwal-cloud` to HACS as a custom
**Integration**, install **Narwal Cloud**, restart Home Assistant, and add
**Narwal Cloud (unofficial)** from **Settings → Devices & services**. Account
login is recommended. Existing token-based entries can use **Reconfigure** to
switch to automatic account login.

Use **Configure** on the integration entry to change the polling interval from
1 to 300 seconds. The default is 1 second.

Credentials remain in the local Home Assistant config entry and are never
written to this repository, diagnostics, or integration logs. Anyone with
access to the HA host or backups may be able to read locally stored secrets, so
protect both. When another account needs the robot, invite it from the primary
Narwal account instead of resetting, transferring, or unbinding the robot.

This project is not affiliated with Narwal. The cloud protocol is undocumented
and may change.

## License

MIT
