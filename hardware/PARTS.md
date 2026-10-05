# 주요 하드웨어 구성

| 구분 | 부품 | 수량 | 역할 |
|---|---|---:|---|
| 메인 제어 | NVIDIA Jetson Orin Nano | 1 | ROS2, 비전, 음성, NLU 및 동작 제어 |
| 모터 제어 | PCA9685 16채널 PWM 드라이버 | 1 | 목·팔 서보 PWM 출력 |
| 보조 제어 | WeMos LOLIN D32 (ESP32) | 1 | 얼굴 LCD 출력 |
| 얼굴 화면 | 3.5인치 ILI9488 SPI LCD | 1 | 로봇 표정 표시 |
| 메인 화면 | 5인치 HDMI LCD | 1 | 주문·상태 화면 |
| 비전 | USB 카메라 | 1 | 얼굴·고개·손 제스처 인식 |
| 음성 | USB 마이크, 스피커 | 각 1 | STT 입력과 TTS 출력 |
| 전원 | MEAN WELL LRS-150F-5 | 1 | 서보용 5 V 전원 |
| 전원 입력 | Inalways 0717-2SCQ | 1 | AC 인렛·스위치·퓨즈 |
| 전원 분배 | 6구 ATO/ATC 퓨즈박스, GND 버스바 | 각 1 | 서보 전원 분기 및 보호 |
| 서보 | DS3218 | 1 | 어깨 루트 관절 |
| 서보 | MG996R | 5 | 목 2축 및 팔 관절 3축 |
| 서보 | MG90S | 3 | 손목 2축 및 그리퍼 |

세부 배선과 채널은 [wiring.md](./wiring.md), [MOTORS.md](./MOTORS.md)를 기준으로 한다. 개별 부품의 사양과 장착 참고사항은 [components/](./components/)에 정리한다.
