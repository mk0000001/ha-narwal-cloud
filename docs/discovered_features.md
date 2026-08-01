# 앱 기능 조사 / App feature survey

Narwal Freo YJCC012와 공식 Android 앱 2.7.03에서 확인한 항목입니다.

## 현재 통합됨 / Integrated

- 배터리, 이동 상태, 청소 상태, 터보 상태
- 시작, 일시정지, 재개, 중지, 충전대 복귀
- Freo Mind, 진공, 물걸레, 진공+물걸레, 진공 후 물걸레
- 흡입력(HA vacuum fan speed 포함), 물걸레 습도, 청소 횟수
- 방/구역 청소, 실시간 지도, 로봇 및 충전기 위치
- 물걸레 세척·건조 시작/종료와 소모품 수명

## 앱에서 확인했으나 명령 검증 필요 / Discovered, command capture required

- 집중 모서리 청소 주기: 매번, 매일, 7일마다
- Freo Mind 청소 전략
- 방해 금지 시간
- 계단 없는 환경 모드, 고지대 모드, 차일드락
- 물걸레 건조 강도, 세제 자동 투입
- 예약 작업, 최대 4개 지도, 지도 편집

이 항목들은 공식 앱 UI에는 존재하지만 공개 API가 없습니다. 실제 요청/응답을
검증하기 전에는 기기 설정을 손상시킬 수 있는 추측 명령을 보내지 않습니다.

These options exist in the official app but have no public API. They will only
be added after their requests and responses are captured and verified.
