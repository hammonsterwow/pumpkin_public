# NLU Experiments

이 디렉터리는 현재 프로젝트의 **NLU 모델 비교·평가 실험과 재현 자료**를 보관합니다.

## KIPS 2026 Item Query 실험

`kips_2026_item_query/`는 KoELECTRA-small 기반 카페 주문 NLU에서 Independent Item Heads와 Item Query Decoder를 동일 데이터 조건으로 비교한 실험 패키지입니다.

주요 내용:

- M0: Independent Item Heads
- M1: Item Query Decoder
- M2: Item Query Decoder + differential LR + multi-order oversampling + weighted loss
- seed 42, 43, 44 반복 실험
- 1-item / 2-item / 3-item / Multi-item / Overall Order Exact Match 평가
- ablation 실험 및 논문용 요약 결과

현재 서비스에서 사용하는 NLU 추론 코드는 루트 `nlu/`를 기준으로 하며, ROS2 통합 실행은 `ros2_ws/src/robot_controller/`를 기준으로 합니다.

현재 저장소에는 최종 모델 비교와 재현에 필요한 실험 자료를 유지합니다.
