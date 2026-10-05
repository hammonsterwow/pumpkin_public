# 서보 전원 ON/OFF 안전 절차

이 절차는 LRS-150F-5, PCA9685와 서보 9개를 안전하게 운용하기 위한 순서이다. Jetson은 PCA9685의 PWM 출력을 제어하고, 사용자는 0717-2SCQ 인렛으로 서보용 5 V 전원을 켜고 끈다.

## 전원 켜기

1. 인렛이 OFF인지 확인하고 로봇팔을 물리적으로 지지한다.
2. Jetson을 먼저 부팅한다.
3. 다음 명령을 실행한다.

~~~bash
cd ~/pumpkin
bash scripts/servo_power_on.sh
~~~

4. 화면 안내에 따라 READY를 입력한다.
5. 인렛을 ON으로 전환한 뒤 ON을 입력한다.
6. [OK] Servo PWM enabled를 확인한 다음 로봇 프로그램을 실행한다.

프로그램은 PWM을 차단한 상태에서 PCA9685를 초기화하고 HOME 값을 기록한 뒤, 서보 전원이 안정되면 출력을 활성화한다.

## HOME 값

~~~text
CH0  = 60    Neck Pitch
CH1  = 90    Neck Yaw
CH4  = 90    Root
CH5  = 90    Arm A1
CH6  = 90    Arm A2
CH7  = 1     Arm B
CH8  = 1     Wrist A
CH9  = 140   Wrist B
CH10 = 179   Gripper
~~~

## 전원 끄기

1. 진행 중인 동작을 끝내고 팔이 HOME으로 복귀했는지 확인한다.
2. 로봇 런타임을 Ctrl+C로 종료한다.
3. 서보 전원이 끊겨도 팔이 떨어지지 않도록 팔을 지지한다.
4. 다음 명령을 실행한다.

~~~bash
cd ~/pumpkin
bash scripts/servo_power_off.sh
~~~

5. 화면 안내에 따라 READY를 입력한다.
6. 팔을 계속 지지한 상태에서 인렛을 OFF로 전환하고 OFF를 입력한다.
7. PWM 차단을 확인한 뒤, 필요하면 Jetson을 정상 종료한다.

~~~bash
sudo shutdown -h now
~~~

Jetson의 종료가 끝나기 전에 전원을 강제로 차단하지 않는다.

## 긴급 PWM 차단

~~~bash
cd ~/pumpkin
python3 scripts/pca9685/servo_power_sequence.py emergency-disable
~~~

안내에 따라 DISABLE을 입력한다. 긴급 차단 시 서보의 holding torque가 즉시 사라져 팔이 떨어질 수 있으므로 정상 종료 대신 사용하지 않는다.

## 금지 사항

- Jetson/PCA9685 초기화 전에 인렛을 먼저 켜지 않는다.
- 팔이 움직이거나 공중에 떠 있는 상태에서 서보 전원을 끄지 않는다.
- Jetson GPIO로 LRS의 고전류 출력을 직접 스위칭하지 않는다.
- 전압 이상, 과열, 냄새 또는 비정상 동작이 있으면 반복 가동하지 않는다.
