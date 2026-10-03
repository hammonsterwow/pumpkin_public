# Pumpkin 문서 목록

## 문서 상태와 기준

저장소 정리 및 문서 기준은 [`REPOSITORY_CLEANUP_2026-08-10.md`](./REPOSITORY_CLEANUP_2026-08-10.md)를 먼저 확인한다.

- **현재 사양/정책 문서**: 새 기능과 리팩터링의 기준으로 사용한다.
- **실험·디버깅 로그**: 특정 시점의 관찰과 해결 기록이며 현재 사양의 최종 기준으로 사용하지 않는다.
- **Legacy/Archive 문서**: 과거 구현을 보존하기 위한 참고 자료다.
- 프로젝트 전체 개요와 실행 진입점은 루트 [`README.md`](../README.md)를 기준으로 한다.

### 현재 중요 정책

- 고객 유형 및 화면 역할: [`service_customer_and_display_policy.md`](./service_customer_and_display_policy.md) → 단골/사전주문 조합별 로봇 응대와 POS 웹·시연 웹·가슴 모니터 웹의 역할을 정의한 현재 서비스 기준
- 메뉴 카탈로그 및 공식 `menu_id`: [`menu_catalog_policy.md`](./menu_catalog_policy.md) → `config/menu_catalog.json`을 서비스 메뉴의 Single Source of Truth로 사용
- 관리자 웹: 기존 `web/` 구현은 보존하며, 신규 관리자 웹은 재구축 예정. 자세한 원칙은 [`REPOSITORY_CLEANUP_2026-08-10.md`](./REPOSITORY_CLEANUP_2026-08-10.md) 참고

## NLU 및 데이터셋

- [`nlu_training_data_gap_guide.md`](./nlu_training_data_gap_guide.md): 다음 NLU 모델 재학습 시 추가해야 할 짧은 후속 답변, 추가 주문, 질문형 발화, 다중 주문, 앞부분 잡음·STT 오류 데이터와 라벨링 원칙
- [`★ structure_b_final_dataset.md`](./★%20structure_b_final_dataset.md): Structure B 데이터셋 설계 및 과거 최종 데이터셋 기록
- [`single_menu_quantity_dataset_summary.md`](./single_menu_quantity_dataset_summary.md): 단일 메뉴 수량 데이터셋 기록

NLU 데이터셋은 **모델의 학습 라벨·출력 구조 기준**이다. 가격, 판매 여부, 서비스용 메뉴 ID 등 운영 메뉴 정보는 `config/menu_catalog.json`을 기준으로 한다.

## 주문·대화 흐름

- [`order_dialogue_rules.md`](./order_dialogue_rules.md): 주문 대화 규칙
- [`order_validation_rules.md`](./order_validation_rules.md): 주문 검증 규칙
- [`response_manager.md`](./response_manager.md): 응답 생성 역할과 규칙
- [`★ order_interaction_flow.md`](./★%20order_interaction_flow.md): 주문 상호작용 흐름 기록
- [`scenario-flows/usecase-flows.md`](./scenario-flows/usecase-flows.md): 서비스 시나리오별 흐름

`★`가 포함된 파일명은 과거 중요도 표시 방식이다. 향후 링크 의존성을 확인한 뒤 일반적인 파일명으로 정리한다.

## API · 앱 · 웹 연동

- [`unified_order_api.md`](./unified_order_api.md): 통합 주문 API
- [`face_enrollment_api.md`](./face_enrollment_api.md): 얼굴 등록 API
- [`firebase_auth_setup.md`](./firebase_auth_setup.md): Firebase 인증 설정
- [`web_team_setup.md`](./web_team_setup.md): 기존 웹 개발/연동 기록

기존 관리자 웹은 현재 참고·연동 확인용으로 보존한다. 신규 관리자 웹 UI/구조는 별도로 재구축할 예정이다.

## Jetson · 실행 환경

- [`JETSON_ENVIRONMENT_STATUS.md`](./JETSON_ENVIRONMENT_STATUS.md): Jetson 환경 상태 기록
- [`jetson_expo_order_manual.md`](./jetson_expo_order_manual.md): Jetson/Expo 주문 연동 매뉴얼
- [`macos_local_run.md`](./macos_local_run.md): macOS 로컬 실행 기록
- 루트 [`JETSON_RUNTIME_README.md`](../JETSON_RUNTIME_README.md): Jetson 런타임 실행 안내

## 하드웨어 연동

- [`motor_controller.md`](./motor_controller.md): 모터 컨트롤러 관련 문서
- 하드웨어 세부 문서는 [`../hardware/README.md`](../hardware/README.md)와 `hardware/` 하위 문서를 참고한다.

## 현장 실험 및 디버깅

- [`2026-09-05_qwen3_smalltalk_standalone_log.md`](./2026-09-05_qwen3_smalltalk_standalone_log.md): 자체 주문 데이터와 규칙만으로 일반 한국어·스몰토크를 처리하는 한계를 정리하고, 기존 koELECTRA/FSM을 유지한 채 Qwen3-0.6B를 `GGUF Q4_K_M + llama.cpp`로 Jetson에서 standalone 검증하기 위한 구조·테스트 항목·fallback 계획을 기록
- [`2026-08-10_stt_respeaker_debug_log.md`](./2026-08-10_stt_respeaker_debug_log.md): Jetson 실기 주문 테스트에서 발견된 STT 복구 문제, ReSpeaker Lite의 ALSA capture/playback 조사 결과, AEC 기반 full-duplex 전환 계획
- [`2026-08-10_robot_interaction_troubleshooting_log.md`](./2026-08-10_robot_interaction_troubleshooting_log.md): 최근 실물 로봇 상호작용 테스트에서 발견한 STT/VAD, 주문 정정·추가, 안내 동작, launcher 문제를 **관찰 → 원인 분석 → 수정 → 검증 → 남은 문제** 순서로 정리
- [`current_order_flow_issues_and_action_plan.md`](./current_order_flow_issues_and_action_plan.md): 주문 흐름 이슈 및 조치 계획 기록

현장 실험 문서는 **증상 → 원인 → 적용한 해결 → 실제 장치 확인 → 미확정 사항 → 다음 실험** 순서로 기록한다. 장기 추적이 필요한 미해결 작업은 GitHub Issue로 분리한다.

실물 주문 흐름이 이상할 때는 로봇 상호작용 트러블슈팅 문서의 **STT → NLU → Decision/FSM → Action 단계별 원인 분리 기준**을 먼저 확인한다.
