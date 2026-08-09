/*
 * 만들기존 호출 버튼 (Q3) — "이 버튼이 시스템 전체를 움직인다"
 * 설계명세서 5.1 · 5.3: 아케이드 버튼 + 버튼 LED 숨쉬기 점멸 + 상태 LED 스트립
 *
 * 결선:
 *   D2 ← 아케이드 버튼 SW (INPUT_PULLUP · 눌림 = LOW)
 *   D3 → 1kΩ → 2N2222 베이스 (버튼 내장 LED 5V 스위칭 · PWM 숨쉬기)
 *   D6 → 74AHCT125 → 330Ω → 상태 LED 스트립 (8~16LED, 보드 5V 급전 가능)
 *
 * 동작:
 *   버튼 1회(디바운싱) → 시리얼 "PRESS" 송신
 *   리눅스 브리지(bridge/button_bridge.py)가 서버 /api/call 호출 후 결과 회신:
 *     'K' 호출 성공 → 초록 스윕
 *     'E' 대기 없음 → 노랑 2회 점멸
 *     'X' 서버 오류 → 빨강 3회 점멸
 *
 * 라이브러리: Adafruit NeoPixel
 */
#include <Adafruit_NeoPixel.h>

#define BTN_PIN    2
#define BTNLED_PIN 3
#define STRIP_PIN  6
#define NUM_LEDS   12

Adafruit_NeoPixel strip(NUM_LEDS, STRIP_PIN, NEO_GRB + NEO_KHZ800);

const unsigned long DEBOUNCE_MS = 40;
const unsigned long LOCKOUT_MS  = 1500;  // 연타 방지 — 관리 뷰와 동일 정책

int lastReading = HIGH;
unsigned long lastChange = 0;
bool pressed = false;
unsigned long lastPress = 0;
unsigned long feedbackUntil = 0;
char feedback = 0;
uint16_t frame = 0;
unsigned long lastFrame = 0;

void setup() {
  Serial.begin(115200);
  pinMode(BTN_PIN, INPUT_PULLUP);
  pinMode(BTNLED_PIN, OUTPUT);
  strip.begin();
  strip.setBrightness(100);
  strip.show();
}

void loop() {
  // ── 버튼 디바운싱 ──
  int reading = digitalRead(BTN_PIN);
  if (reading != lastReading) { lastChange = millis(); lastReading = reading; }
  if (millis() - lastChange > DEBOUNCE_MS) {
    if (reading == LOW && !pressed && millis() - lastPress > LOCKOUT_MS) {
      pressed = true;
      lastPress = millis();
      Serial.println("PRESS");
    }
    if (reading == HIGH) pressed = false;
  }

  // ── 브리지 응답 수신 ──
  while (Serial.available()) {
    char c = Serial.read();
    if (c == 'K' || c == 'E' || c == 'X') {
      feedback = c;
      feedbackUntil = millis() + (c == 'K' ? 1500 : 1200);
    }
  }

  // ── 프레임 (약 30fps) ──
  if (millis() - lastFrame < 33) return;
  lastFrame = millis();
  frame++;

  // 버튼 내장 LED: 숨쉬기 점멸 (삼각파 PWM)
  int ph = (frame * 3) & 0xFF;
  int breath = ph < 128 ? ph : 255 - ph;              // 0~127
  analogWrite(BTNLED_PIN, 30 + breath * 225 / 127);   // 30~255

  // 상태 스트립
  if (millis() < feedbackUntil) drawFeedback();
  else drawIdle();
  strip.show();
}

/* 대기: 은은한 달 노랑 펄스 (떡집 팔레트) */
void drawIdle() {
  int ph = (frame * 2) & 0xFF;
  int s = ph < 128 ? ph : 255 - ph;
  int lvl = 30 + s * 120 / 127;
  for (int i = 0; i < NUM_LEDS; i++)
    strip.setPixelColor(i, lvl, lvl * 70 / 100, 0);
}

void drawFeedback() {
  if (feedback == 'K') {                       // 성공: 초록 스윕
    int head = (frame * 2) % (NUM_LEDS * 2);
    for (int i = 0; i < NUM_LEDS; i++)
      strip.setPixelColor(i, 0, i <= head ? 220 : 0, 30);
  } else if (feedback == 'E') {                // 대기 없음: 노랑 점멸
    bool on = (millis() / 300) % 2 == 0;
    for (int i = 0; i < NUM_LEDS; i++)
      strip.setPixelColor(i, on ? 230 : 0, on ? 180 : 0, 0);
  } else {                                     // 오류: 빨강 점멸
    bool on = (millis() / 200) % 2 == 0;
    for (int i = 0; i < NUM_LEDS; i++)
      strip.setPixelColor(i, on ? 230 : 0, 0, 0);
  }
}
