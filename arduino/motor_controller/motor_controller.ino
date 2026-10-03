#include <Servo.h>

Servo panServo;
Servo tiltServo;

const int PAN_SERVO_PIN = 10;
const int TILT_SERVO_PIN = 9;

// Calibrated physical angles for the current neck assembly.
const int PAN_CENTER_ANGLE = 90;
const int PAN_LEFT_ANGLE = 60;
const int PAN_RIGHT_ANGLE = 120;
const int TILT_CENTER_ANGLE = 60;  // Physical forward-facing position.
const int TILT_DOWN_ANGLE = 125;   // Physical nod-down position.

// Smaller values produce faster motion.
const int STEP_DELAY_MS = 9;

int currentPanAngle = PAN_CENTER_ANGLE;
int currentTiltAngle = TILT_CENTER_ANGLE;

void moveSmooth(Servo &servo, int &currentAngle, int targetAngle) {
  targetAngle = constrain(targetAngle, 0, 180);

  while (currentAngle != targetAngle) {
    currentAngle += (currentAngle < targetAngle) ? 1 : -1;
    servo.write(currentAngle);
    delay(STEP_DELAY_MS);
  }

  // Reassert the absolute target so repeated gestures do not accumulate drift.
  currentAngle = targetAngle;
  servo.write(targetAngle);
}

void centerNeck() {
  moveSmooth(panServo, currentPanAngle, PAN_CENTER_ANGLE);
  moveSmooth(tiltServo, currentTiltAngle, TILT_CENTER_ANGLE);
}

void performYesGesture() {
  // Always start and finish from the calibrated forward-facing pose.
  centerNeck();

  // Forward -> down -> forward -> down -> forward.
  for (int i = 0; i < 2; i++) {
    moveSmooth(tiltServo, currentTiltAngle, TILT_DOWN_ANGLE);
    moveSmooth(tiltServo, currentTiltAngle, TILT_CENTER_ANGLE);
  }

  centerNeck();
}

void performNoGesture() {
  // Always start and finish from the calibrated forward-facing pose.
  centerNeck();

  // Forward -> left -> forward -> right -> forward -> left -> forward.
  moveSmooth(panServo, currentPanAngle, PAN_LEFT_ANGLE);
  moveSmooth(panServo, currentPanAngle, PAN_CENTER_ANGLE);

  moveSmooth(panServo, currentPanAngle, PAN_RIGHT_ANGLE);
  moveSmooth(panServo, currentPanAngle, PAN_CENTER_ANGLE);

  moveSmooth(panServo, currentPanAngle, PAN_LEFT_ANGLE);
  moveSmooth(panServo, currentPanAngle, PAN_CENTER_ANGLE);

  centerNeck();
}

void setup() {
  Serial.begin(115200);

  panServo.attach(PAN_SERVO_PIN);
  tiltServo.attach(TILT_SERVO_PIN);

  panServo.write(PAN_CENTER_ANGLE);
  tiltServo.write(TILT_CENTER_ANGLE);
  delay(400);

  Serial.println("READY");
}

void loop() {
  if (!Serial.available()) {
    return;
  }

  String command = Serial.readStringUntil('\n');
  command.trim();
  command.toUpperCase();

  if (command == "YES") {
    performYesGesture();
  } else if (command == "NO") {
    performNoGesture();
  } else if (command == "CENTER") {
    centerNeck();
  }
}
