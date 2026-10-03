/*
  Pumpkin Robot Face Display for ESP32 + 3.5 inch ILI9488 SPI LCD

  Purpose
  - Receives face commands from Jetson Nano through USB Serial.
  - Draws one of five LCD face states on a 480x320 SPI TFT LCD.

  Supported commands
  - NEUTRAL
  - SMILE
  - HAPPY
  - QUESTION
  - ERROR

  Required library
  - TFT_eSPI by Bodmer

  Important
  - This code assumes the LCD is used in landscape mode: 480 x 320.
  - Before uploading, set TFT_eSPI User_Setup.h or a custom setup file for:
      Driver: ILI9488
      Resolution: 480x320
      SPI pins matching your ESP32 wiring
  - Touch pins are not used in this first version.
*/

#include <TFT_eSPI.h>
#include <SPI.h>
#include <math.h>

TFT_eSPI tft = TFT_eSPI();

// LCD size in landscape mode
const int W = 480;
const int H = 320;

// Colors converted from the Python pygame prototype
const uint16_t PANEL = TFT_eSPI::color565(13, 30, 47);     // dark LCD background
const uint16_t FACE  = TFT_WHITE;                         // white face

// The Python prototype used 960x540 coordinates.
// These helpers scale the same face layout to 480x320.
int sx(float x) {
  return (int)(x * W / 960.0f);
}

int sy(float y) {
  return (int)(y * H / 540.0f);
}

void drawBackground() {
  tft.fillScreen(PANEL);
}

void drawThickLine(int x1, int y1, int x2, int y2, int thickness, uint16_t color) {
  // Simple thick-line helper using repeated lines plus round endpoints.
  float dx = x2 - x1;
  float dy = y2 - y1;
  float len = sqrt(dx * dx + dy * dy);

  if (len == 0) {
    tft.fillCircle(x1, y1, thickness / 2, color);
    return;
  }

  float nx = -dy / len;
  float ny = dx / len;
  int half = thickness / 2;

  for (int i = -half; i <= half; i++) {
    int ox = (int)(nx * i);
    int oy = (int)(ny * i);
    tft.drawLine(x1 + ox, y1 + oy, x2 + ox, y2 + oy, color);
  }

  tft.fillCircle(x1, y1, half, color);
  tft.fillCircle(x2, y2, half, color);
}

void drawThickArc(int x, int y, int w, int h, int startDeg, int endDeg, int thickness, bool upperArc, uint16_t color) {
  // Draws a thick arc with line segments.
  // upperArc=true  -> cap shape like smiling eyes: ∩
  // upperArc=false -> cup shape like smiling mouth: ∪
  float cx = x + w / 2.0f;
  float cy = y + h / 2.0f;
  float rx = w / 2.0f;
  float ry = h / 2.0f;

  int prevX = 0;
  int prevY = 0;
  bool hasPrev = false;

  for (int deg = startDeg; deg <= endDeg; deg += 4) {
    float rad = deg * PI / 180.0f;
    int px = (int)(cx + rx * cos(rad));
    int py;

    if (upperArc) {
      py = (int)(cy - ry * sin(rad));
    } else {
      py = (int)(cy + ry * sin(rad));
    }

    if (hasPrev) {
      drawThickLine(prevX, prevY, px, py, thickness, color);
    }

    prevX = px;
    prevY = py;
    hasPrev = true;
  }
}

void drawSmileMouth(int x, int y, int w, int h, int thickness) {
  drawThickArc(sx(x), sy(y), sx(w), sy(h), 0, 180, sx(thickness), false, FACE);
}

void drawSmileEye(int x, int y, int w, int h, int thickness) {
  drawThickArc(sx(x), sy(y), sx(w), sy(h), 0, 180, sx(thickness), true, FACE);
}

void drawNeutral() {
  drawBackground();

  // Round eyes
  tft.fillCircle(sx(300), sy(220), sx(42), FACE);
  tft.fillCircle(sx(660), sy(220), sx(42), FACE);

  // Small smiling mouth
  drawSmileMouth(420, 285, 120, 80, 16);
}

void drawSmile() {
  drawBackground();

  // Smiling eyes
  drawSmileEye(245, 190, 120, 80, 14);
  drawSmileEye(595, 190, 120, 80, 14);

  // Soft smiling mouth
  drawSmileMouth(415, 285, 130, 90, 16);
}

void drawHappy() {
  drawBackground();

  // Happy eyes: > <
  // Left eye: >
  drawThickLine(sx(260), sy(190), sx(345), sy(245), sx(16), FACE);
  drawThickLine(sx(260), sy(300), sx(345), sy(245), sx(16), FACE);

  // Right eye: <
  drawThickLine(sx(700), sy(190), sx(615), sy(245), sx(16), FACE);
  drawThickLine(sx(700), sy(300), sx(615), sy(245), sx(16), FACE);

  // Cute smiling mouth
  drawSmileMouth(420, 315, 120, 70, 14);
}

void drawQuestion() {
  drawBackground();

  // Round eyes
  tft.fillCircle(sx(300), sy(225), sx(45), FACE);
  tft.fillCircle(sx(660), sy(225), sx(45), FACE);

  // Eyebrows
  drawThickLine(sx(245), sy(150), sx(355), sy(135), sx(12), FACE);
  drawThickLine(sx(605), sy(135), sx(715), sy(150), sx(12), FACE);

  // O mouth
  tft.fillCircle(sx(480), sy(320), sx(42), FACE);
  tft.fillCircle(sx(480), sy(320), sx(22), PANEL);

  // Question mark
  tft.setTextColor(FACE, PANEL);
  tft.setTextFont(1);
  tft.setTextSize(8);
  tft.setCursor(sx(760), sy(70));
  tft.print("?");
}

void drawError() {
  drawBackground();

  // X eyes
  drawThickLine(sx(250), sy(175), sx(350), sy(275), sx(14), FACE);
  drawThickLine(sx(350), sy(175), sx(250), sy(275), sx(14), FACE);

  drawThickLine(sx(610), sy(175), sx(710), sy(275), sx(14), FACE);
  drawThickLine(sx(710), sy(175), sx(610), sy(275), sx(14), FACE);

  // Flat mouth
  drawThickLine(sx(430), sy(335), sx(530), sy(335), sx(14), FACE);

  // Exclamation mark
  tft.setTextColor(FACE, PANEL);
  tft.setTextFont(1);
  tft.setTextSize(8);
  tft.setCursor(sx(775), sy(70));
  tft.print("!");
}

void drawFace(String face) {
  face.trim();
  face.toUpperCase();

  if (face == "NEUTRAL") {
    drawNeutral();
  } else if (face == "SMILE") {
    drawSmile();
  } else if (face == "HAPPY") {
    drawHappy();
  } else if (face == "QUESTION") {
    drawQuestion();
  } else if (face == "ERROR") {
    drawError();
  } else {
    // Unknown command is treated as QUESTION.
    drawQuestion();
  }
}

void setup() {
  Serial.begin(115200);
  delay(500);

  tft.init();

  // Landscape mode. If the screen appears rotated, try 1 or 3.
  tft.setRotation(1);

  drawNeutral();

  Serial.println("Pumpkin ESP32 LCD face display ready.");
  Serial.println("Send one of: NEUTRAL, SMILE, HAPPY, QUESTION, ERROR");
}

void loop() {
  if (Serial.available()) {
    String face = Serial.readStringUntil('\n');
    drawFace(face);
  }
}
