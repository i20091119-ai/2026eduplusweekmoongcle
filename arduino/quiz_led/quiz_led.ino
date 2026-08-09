/*
 * 퀴즈존 LED 연출 (Q1 · Q2 공용) — WS2812B 애니메이션 3종
 * 설계명세서 5.1: 대기(은은한 순환) / 정답(초록 플래시) / 호출(스테이션 색 웨이브)
 *
 * 결선 (설계명세서 5.3):
 *   D6 → 74AHCT125(1A) → 1Y → 330Ω → WS2812B DIN
 *   스트립 전원은 별도 5V 4A 어댑터 (1000uF 병렬) · GND 공통 필수
 *
 * 리눅스 측 브리지(bridge/led_bridge.py)가 시리얼로 한 글자 명령 전송:
 *   'A'/'B' : 스테이션 색 설정 (부팅 직후 1회 — A 주황 / B 파랑)
 *   'I'     : 대기 애니메이션
 *   'C'     : 정답 플래시 (끝나면 자동으로 대기 복귀)
 *   'W'     : 호출 웨이브 ('I' 수신 또는 15초 후 자동 복귀)
 *
 * 라이브러리: Adafruit NeoPixel (라이브러리 매니저에서 설치)
 */
#include <Adafruit_NeoPixel.h>

#define LED_PIN    6
#define NUM_LEDS   60      // 디스플레이 테두리 실측 후 조정
#define BRIGHTNESS 120     // 0~255 — 전원 여유에 맞춰 조정

Adafruit_NeoPixel strip(NUM_LEDS, LED_PIN, NEO_GRB + NEO_KHZ800);

char mode = 'I';
char station = 'A';
unsigned long modeStart = 0;
unsigned long lastFrame = 0;
uint16_t frame = 0;

const unsigned long WAVE_TIMEOUT_MS  = 15000;  // 호출 웨이브 자동 종료(브리지 정지 대비)
const unsigned long FLASH_DURATION_MS = 1500;  // 정답 플래시 길이

uint32_t stationColor() {
  // 스테이션 고유색 — 멀리서도 누가 일어날 차례인지 식별 (5.1)
  // 뭉클 떡집 팔레트: A = 달 노랑, B = 하늘색
  if (station == 'B') return strip.Color(40, 140, 255);  // B: 하늘색
  return strip.Color(255, 190, 30);                      // A: 달 노랑
}

void setup() {
  Serial.begin(115200);
  strip.begin();
  strip.setBrightness(BRIGHTNESS);
  strip.show();
  modeStart = millis();
}

void setMode(char m) {
  mode = m;
  modeStart = millis();
  frame = 0;
}

void loop() {
  // ── 명령 수신 ──
  while (Serial.available()) {
    char c = Serial.read();
    if (c == 'A' || c == 'B') station = c;
    else if (c == 'I' || c == 'C' || c == 'W') setMode(c);
  }

  // ── 자동 복귀 ──
  unsigned long elapsed = millis() - modeStart;
  if (mode == 'C' && elapsed > FLASH_DURATION_MS) setMode('I');
  if (mode == 'W' && elapsed > WAVE_TIMEOUT_MS)  setMode('I');

  // ── 프레임 갱신 (약 30fps) ──
  if (millis() - lastFrame < 33) return;
  lastFrame = millis();
  frame++;

  if (mode == 'I') animIdle();
  else if (mode == 'C') animCorrect(elapsed);
  else animWave();
  strip.show();
}

/* 대기: 스테이션 색이 은은하게 순환 — 밝기 파도가 천천히 흐름 */
void animIdle() {
  uint32_t c = stationColor();
  uint8_t r = (uint8_t)(c >> 16), g = (uint8_t)(c >> 8), b = (uint8_t)c;
  for (int i = 0; i < NUM_LEDS; i++) {
    // 0.2~1.0 사이 사인 파형 (정수 근사)
    int phase = (i * 256 / NUM_LEDS + frame * 2) & 0xFF;
    int s = phase < 128 ? phase : 255 - phase;      // 삼각파 0~127
    int lvl = 50 + s * 155 / 127;                   // 50~205
    strip.setPixelColor(i, r * lvl / 255, g * lvl / 255, b * lvl / 255);
  }
}

/* 정답: 초록 플래시 3회 */
void animCorrect(unsigned long elapsed) {
  bool on = (elapsed / 250) % 2 == 0;
  uint32_t c = on ? strip.Color(0, 200, 40) : 0;
  for (int i = 0; i < NUM_LEDS; i++) strip.setPixelColor(i, c);
}

/* 호출: 스테이션 색 웨이브가 만들기존 방향으로 흐름
 * (스트립 설치 방향에 따라 방향이 반대면 WAVE_REVERSE를 1로) */
#define WAVE_REVERSE 0
void animWave() {
  uint32_t c = stationColor();
  uint8_t r = (uint8_t)(c >> 16), g = (uint8_t)(c >> 8), b = (uint8_t)c;
  int head = (frame * 2) % NUM_LEDS;
  for (int i = 0; i < NUM_LEDS; i++) {
    int pos = WAVE_REVERSE ? NUM_LEDS - 1 - i : i;
    int dist = (head - pos + NUM_LEDS) % NUM_LEDS;  // 웨이브 꼬리 길이 12
    int lvl = dist < 12 ? 255 - dist * 20 : 0;
    strip.setPixelColor(i, r * lvl / 255, g * lvl / 255, b * lvl / 255);
  }
}
