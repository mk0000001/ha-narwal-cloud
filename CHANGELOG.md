# 변경 기록 / Changelog

## 0.9.0

### 한국어

- 기본 상태 갱신 주기를 30초에서 1초로 단축했습니다.
- 통합 **구성** 메뉴에서 1~300초 범위로 폴링 주기를 변경할 수 있습니다.
- HA 기본 옵션 흐름의 자동 다시 읽기를 사용해 토큰 자동 저장이 불필요한 재시작을
  일으키지 않습니다.
- 1초 폴링을 HA Core 2026.7.4에서 반복 검증했으며 429, 인증 오류 및 엔티티
  `unavailable` 재발이 없음을 확인했습니다.
- 지도 갱신은 5분 간격의 별도 작업으로 유지되어 빠른 상태 폴링과 겹치지 않으며,
  지도 응답 실패가 로봇 상태 엔티티를 중단시키지 않습니다.
- YJCC012가 대기 중 `/map/get_map` MQTT 요청에 응답하지 않는 경우 지도 엔티티는
  정상 상태를 유지하지만 실제 지도 내용은 비어 있을 수 있습니다. 공식 앱의 저장 지도는
  정상임을 확인했으며, 이는 1초 폴링과 무관한 기존 펌웨어/세션 제한입니다.

### English

- Reduced the default state polling interval from 30 seconds to 1 second.
- Added a 1–300 second polling option under the integration's **Configure** menu.
- Uses Home Assistant's native options-flow reload support, avoiding reloads
  when rotated tokens are persisted.
- Repeatedly tested one-second polling on HA Core 2026.7.4 without HTTP 429,
  authentication errors, or entities becoming unavailable.
- Map refresh remains an isolated five-minute task so map failures cannot stop
  the primary robot-state entities.
- Known limitation: some idle YJCC012 sessions do not answer `/map/get_map`.
  In that case the camera entity stays available but its map payload is empty;
  this is independent of the one-second state polling change.

## 0.8.0

- 나르왈 계정 로그인, 자동 토큰 재발급, 한국어/영어 구성 흐름을 추가했습니다.
- Added Narwal account login, automatic token recovery, and Korean/English flows.
- 앱의 공식 방별 템플릿을 사용하도록 구역 청소를 수정했습니다.
- Fixed segment cleaning to use the app's official per-room templates.
- 시간대 계산 오류로 약 1분 뒤 모든 엔티티가 unavailable이 되던 문제를 수정했습니다.
- Fixed the timezone arithmetic crash that made all entities unavailable.
