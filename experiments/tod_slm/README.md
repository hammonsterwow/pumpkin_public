# Task-Oriented Dialogue SLM Experiments

이 디렉터리는 Qwen3-0.6B 기반 Task-Oriented Dialogue 모델의 데이터 생성, 검수, 학습 및 평가 실험을 보관합니다.

실제 로봇 주문 시스템의 기본 NLU는 KoELECTRA 기반 구조를 사용하며, 이 디렉터리의 Qwen 모델은 대화 상태 추적과 구조화 응답 생성을 검토하기 위한 별도 실험입니다.

- `data_generation/`: 규칙 기반 TOD 데이터 생성 및 Qwen SFT 형식 변환
- `review/`: 생성 데이터 표본 검수 도구
- `training/`: Qwen3-0.6B LoRA 학습·평가 및 오류 분석
