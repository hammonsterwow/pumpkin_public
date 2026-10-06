# Pumpkin 시연 반복 테스트 시나리오

실물 시연 직전에 STT → NLU → Decision/FSM → Response → Action → Hardware 흐름을 반복 확인하기 위한 수동 검증 문서입니다.

## 실행

```bash
cd ~/pumpkin_public
git switch main
git pull --ff-only
bash scripts/run_robot_with_monitor.sh
```

기본 로그는 다음 디렉터리에 생성됩니다.

```text
/tmp/pumpkin-logs/
```

문제 발생 시 먼저 관련 노드 로그를 확인합니다.

```bash
tail -n 100 /tmp/pumpkin-logs/stt_node.log
tail -n 100 /tmp/pumpkin-logs/nlu_node.log
tail -n 100 /tmp/pumpkin-logs/decision_node.log
tail -n 100 /tmp/pumpkin-logs/action_node.log
tail -n 100 /tmp/pumpkin-logs/motor_controller_node.log
```

## P0 핵심 시나리오

현재 사람 감지는 주문 세션을 준비하고, 실제 주문 시작은 wake phrase `주문할게요` 이후 진행됩니다.

| ID | 입력/행동 | 기대 결과 |
|---|---|---|
| S01 | 고객 감지 → `주문할게요` → `아이스 아메리카노 한 잔 주세요` | 메뉴/온도/수량 추출 후 주문 확인 |
| S02 | `아이스 두 잔 주세요` → 메뉴 질문에 `아메리카노요` | 기존 ICE/2를 보존하고 메뉴만 보충 |
| S03 | `아메리카노 한 잔 주세요` → 온도 질문에 `따뜻하게요` | HOT만 보충한 뒤 확인 |
| S04 | `아이스 카페라떼 주세요` → 수량 질문에 `두 잔이요` | quantity=2 적용 |
| S05 | 수량 질문 중 손가락 3개 | `THREE_FINGERS` → quantity=3 |
| S06 | 주문 확인 질문에 고개 끄덕임 | NOD를 긍정 입력으로 처리 |
| S07 | 주문 확인에 `아니요` 후 수량/온도 수정 | 수정 후 전체 주문을 다시 확인 |
| S08 | 복수 메뉴 한 문장 주문 | 각 메뉴의 온도·수량 관계가 섞이지 않음 |
| S09 | 주문 확인 중 추가 메뉴 요청 | 기존 주문을 유지하고 새 항목 추가 후 재확인 |
| S10 | 진행 중 주문 취소 | 현재 주문을 비우고 다음 세션에 남기지 않음 |

## P1 비언어·음성 안정성

| ID | 입력/행동 | 기대 결과 |
|---|---|---|
| S11 | 수량 질문에서 손가락 1~5개 각각 사용 | ONE~FIVE_FINGERS가 1~5로 대응 |
| S12 | 수량 질문이 아닌 상태에서 손가락 표시 | 주문 수량이 변경되지 않음 |
| S13 | 주문 확인 중 NOD/SHAKE | 네/아니요와 같은 의미로 처리 |
| S14 | TTS 재생 중 침묵 | 로봇 음성이 사용자 STT로 재입력되지 않음 |
| S15 | TTS 종료 직후 짧게 `네` | 다음 listening turn에서 응답을 놓치지 않음 |
| S16 | 침묵/너무 작은 음성 | 가짜 주문을 만들지 않고 회복 가능한 재질문 수행 |
| S17 | 오디오 장치 오류 | 무한 재질문하지 않고 runtime 오류 상태로 중단 |

## P1 정책·예외

| ID | 입력/행동 | 기대 결과 |
|---|---|---|
| S18 | 지원하지 않는 메뉴 | 임의 메뉴로 치환하지 않고 지원 범위 안내 |
| S19 | ICE 전용 메뉴에 HOT 요청 | 잘못된 HOT 주문을 확정하지 않음 |
| S20 | 누락 슬롯 답변이 모호함 | 임의값을 채우지 않고 필요한 정보를 다시 질문 |
| S21 | 등록 고객 얼굴 인식 | 올바른 고객 context만 개인화에 사용 |
| S22 | APP 주문이 READY | 실제 주문 내용과 픽업 위치 안내 후 TTS 종료 뒤 PICKED_UP |
| S23 | 사전주문 조회 실패 | 타인의 주문을 추측하지 않고 일반 흐름 유지 |

## P2 세션·Cloud/POS

| ID | 입력/행동 | 기대 결과 |
|---|---|---|
| S24 | 주문 중 잠깐 카메라 밖으로 이동 | 활성 주문이 임의 초기화되지 않음 |
| S25 | 주문 완료 후 퇴장→새 고객 등장 | 새 세션에서 이전 주문이 남지 않음 |
| S26 | 실제 ROBOT 주문 종료 | Cloud Relay에 최종 주문이 한 번만 등록 |
| S27 | POS DEMO MODE APP 주문 | RECEIVED→PREPARING→READY에서 멈춤 |
| S28 | POS DEMO MODE ROBOT 주문 | READY 이후 PICKED_UP까지 진행 |
| S29 | 5인치 화면 | 내부 JSON/confidence 대신 고객용 주문 상태만 표시 |

## 합격 기준

- P0 S01~S10은 모두 통과합니다.
- 핵심 주문·TTS/STT·복수 주문 시나리오는 여러 번 반복해 동일하게 동작하는지 확인합니다.
- 비언어 기능을 시연에 포함하면 손 수량과 NOD/SHAKE를 실제 시연 거리에서 확인합니다.
- Cloud/POS/얼굴 픽업을 시연하면 S21~S28까지 같은 네트워크 환경에서 확인합니다.

## 실패 기록

```text
시나리오:
실제 입력/행동:
실제 결과:
재현 횟수:

처음 이상이 보인 단계:
[ ] STT
[ ] NLU
[ ] Decision/FSM
[ ] Response
[ ] Action
[ ] Vision
[ ] Face
[ ] Motor
[ ] Cloud/POS

관련 로그:
```

판정 순서는 입력(STT/Vision) → NLU → Decision → Response → Action → 실제 장치/Cloud 순으로 따라가며 최초로 달라진 지점을 원인 후보로 잡습니다.
