# Jetson 최종 메인 디스플레이: 5인치 HDMI LCD

현재 개발 단계에서는 LG 외부 모니터를 사용하고 있지만, **최종 로봇에는 5인치 HDMI LCD를 Jetson의 메인 화면으로 장착**합니다.

> 이 디스플레이는 머리에 들어가는 3.5인치 ILI9488 얼굴 LCD와 별개의 장치입니다.
>
> - 5인치 HDMI LCD: Jetson 화면·관리 UI·상태 표시
> - 3.5인치 ILI9488 LCD: ESP32가 구동하는 로봇 표정 표시

## 연결 구조

```text
Jetson Orin Nano
    │
    │ DisplayPort
    ▼
CODEWAY DP-to-HDMI 케이블
    │
    │ HDMI
    ▼
5인치 HDMI LCD
    │
    │ USB 5 V 전원
    ▼
MXW-10W2U 5 V / 2.1 A 어댑터
```

현재 사진에서 Jetson 화면 출력이 정상적으로 표시되는 것을 확인했습니다.

## LCD 실물 확인 사양

| 항목 | 내용 |
|---|---|
| 제품 표기 | `5inch HDMI Display` |
| 해상도 | 800 × 480 px |
| 영상 입력 | 표준 HDMI 입력 |
| 터치 컨트롤러 | XPT2046 |
| 터치 방식 | 4선식 저항막 터치로 판매되는 계열 |
| 보드 리비전 | Rev3.3 |
| 전원 | USB 5 V 입력 |
| 후면 확장 | 2×13 GPIO 헤더, SPI 터치 관련 핀 표기 |
| 보드 표기 핀 | 5V, 5V, GND, MI, MO, SCK, GND, CS, IRQ 등 |
| 백라이트 | 후면 Backlight ON/OFF 슬라이드 스위치 |
| 현재 영상 연결 | Jetson DisplayPort → DP-to-HDMI → LCD HDMI |
| 현재 전원 연결 | 5 V USB 어댑터 → LCD 전원 포트 |

## 전원 어댑터

실물 라벨 기준 사양입니다.

| 항목 | 내용 |
|---|---|
| 모델 | MXW-10W2U |
| 입력 | AC 100~240 V, 50/60 Hz, 0.5 A |
| 출력 | DC 5 V, 2.1 A |
| 최대 출력 | 약 10.5 W |
| 제조년월 | 2024-03 |
| 용도 | 5인치 HDMI LCD 전용 전원 |

## LG 외부 모니터와의 관계

- LG FLATRON E2351VQ-BN은 현재 개발·설정 단계에서 사용하는 임시 외부 모니터입니다.
- 최종 조립 후 Jetson의 기본 화면 출력 대상은 5인치 HDMI LCD입니다.
- LG 모니터와 전원 어댑터는 최종 로봇 내부 부품으로 포함하지 않고, 개발·정비용 장비로 구분합니다.
- DP-to-HDMI 케이블은 최종적으로 5인치 LCD의 HDMI 입력에 연결합니다.

## 3.5인치 얼굴 LCD와 구분

| 구분 | 5인치 HDMI LCD | 3.5인치 ILI9488 LCD |
|---|---|---|
| 역할 | Jetson 메인 화면·관리 UI | 로봇 얼굴 표정 출력 |
| 제어 장치 | Jetson Orin Nano | WeMos LOLIN D32 ESP32 |
| 영상 인터페이스 | HDMI | 4-wire SPI |
| 해상도 | 800 × 480 | 480 × 320 |
| 전원 | 별도 USB 5 V 어댑터 | ESP32 연결 전원 계획 |
| 설치 위치 | 로봇 본체의 사용자 화면 | 로봇 머리 |

## 남은 시험

- [ ] Ubuntu에서 800 × 480 해상도 고정 및 재부팅 후 유지 확인
- [ ] LCD 전원 어댑터 연결 상태에서 장시간 화면 출력 시험
- [ ] 터치 입력 장치 인식 및 좌표 보정 확인
- [ ] Backlight 스위치와 화면 밝기 동작 확인
- [ ] 최종 프레임 장착 후 HDMI·전원 케이블 빠짐 방지 구조 적용
- [ ] LG 모니터 제거 후 5인치 LCD 단독 부팅 화면 출력 확인

## 사양 출처 주의

후면 보드에 `5inch HDMI Display`, `800X480 Pixel`, `XPT2046 Touch Controller`, `Rev3.3`가 직접 표기되어 있습니다. 동일한 외형의 제품은 여러 판매처에서 유통되므로, 제조사와 정확한 SKU는 실물 포장 또는 구매 내역 확인 전까지 확정하지 않습니다.
