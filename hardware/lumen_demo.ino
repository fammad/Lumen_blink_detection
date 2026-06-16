/*
  lumen_demo.ino

  Lumen dome firmware. Auto ambient state (CALM / ATTENTION / BREAK) is
  driven by main.py over serial, based on live blink-rate risk scoring.
  The physical button overrides locally: tap toggles pause, hold starts
  or cancels the breathing exercise. Mirrors state.py's DomeState enum.

  Hardware (locked 2026-05-09 / 2026-05-13 sessions):
    NeoPixel ring DI -> GPIO 5
    Button           -> GPIO 4 (INPUT_PULLUP, other leg to GND)
    Brightness       = 150
    Color order      = NEO_GRB

  Serial (115200 baud, sent by main.py on every auto-state change):
    C   auto state -> CALM
    A   auto state -> ATTENTION
    B   auto state -> BREAK
  Unrecognized bytes are ignored. Commands received while the button has
  taken over (PAUSED or BREATHING) are stored but not applied until the
  button lets go.

  Button:
    tap  (<500ms):   toggle PAUSED (flat grey, sensing effectively idle)
    hold (>=1000ms): start / cancel the breathing exercise
    500-999ms:       dead zone, discarded (ambiguous gesture)
*/

#include <Adafruit_NeoPixel.h>

#define LED_PIN     5
#define BUTTON_PIN  4
#define NUM_LEDS    16

Adafruit_NeoPixel strip(NUM_LEDS, LED_PIN, NEO_GRB + NEO_KHZ800);


// ============================================================
// PRESETS (colors locked 2026-05-13)
// ============================================================

struct Preset {
  const char*   name;
  uint16_t      hue;
  uint8_t       saturation;
  uint8_t       vMin;
  uint8_t       vMax;
  unsigned long cycleMs;
};

const Preset PRESETS[] = {
  { "CALM",      6500,  90, 100, 255, 8000 },  // warm white
  { "ATTENTION", 5000, 255, 100, 255, 4000 },  // amber
  { "BREAK",        0, 255, 130, 220, 4000 },  // red, compressed amplitude so it visibly withdraws
};

const int PRESET_CALM      = 0;
const int PRESET_ATTENTION = 1;
const int PRESET_BREAK     = 2;


// ============================================================
// BREATHING EXERCISE (4-7-8 pattern, green)
// ============================================================

const uint16_t      BRTH_HUE    = 22000;
const uint8_t       BRTH_SAT    = 200;
const unsigned long INHALE_MS   = 4000;
const unsigned long HOLD_MS     = 7000;
const unsigned long EXHALE_MS   = 8000;
const int           BRTH_CYCLES = 2;      // then back to auto state

// ============================================================
// MODE / STATE
// ============================================================

enum Mode { AUTO, BREATHING_EXERCISE, PAUSED };

Mode currentMode = AUTO;
int  autoPreset  = PRESET_CALM;   // last state received from main.py

unsigned long cycleStartMs             = 0;
float         currentBrightness        = 0.0;
bool          startNextCycleFromBlack  = true;

int           breathCycleCount    = 0;
unsigned long breathCycleStartMs  = 0;

// Fade to black between state changes instead of a hard cut.
bool          isTransitioning       = false;
unsigned long transitionStartMs     = 0;
uint8_t       transitionStartValue  = 0;
int           pendingPreset         = PRESET_CALM;
Mode          pendingMode           = AUTO;
const unsigned long FADE_MS = 800;

// Button, debounced
const unsigned long DEBOUNCE_MS = 30;
const unsigned long TAP_MAX_MS  = 500;
const unsigned long HOLD_MIN_MS = 1000;


// ============================================================
// SETUP
// ============================================================

void setup() {
  Serial.begin(115200);
  pinMode(BUTTON_PIN, INPUT_PULLUP);

  strip.begin();
  strip.setBrightness(150);
  strip.show();

  cycleStartMs = millis();

  Serial.println();
  Serial.println("=== Lumen ===");
  Serial.println("Auto state via serial: C=CALM  A=ATTENTION  B=BREAK");
  Serial.println("Button: tap=pause, hold=breathing");
}


// ============================================================
// LOOP
// ============================================================

void loop() {
  handleSerial();
  handleButton();
  render(millis());
  delay(20);
}


// ============================================================
// SERIAL INPUT (C/A/B from main.py)
// ============================================================

void handleSerial() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') continue;
    applyAutoCommand(c);
  }
}

void applyAutoCommand(char c) {
  int newPreset;
  switch (c) {
    case 'C': newPreset = PRESET_CALM;      break;
    case 'A': newPreset = PRESET_ATTENTION; break;
    case 'B': newPreset = PRESET_BREAK;     break;
    default:
      return;  // unknown byte, ignore
  }

  autoPreset = newPreset;

  // Button override in progress: store the value, apply it once the
  // override ends (see onTap and renderBreathingExercise).
  if (currentMode == AUTO) {
    startTransitionTo(AUTO, newPreset);
  }
}


// ============================================================
// BUTTON (tap = pause, hold = breathing)
// ============================================================

void handleButton() {
  static bool lastPressed = false;
  static unsigned long lastEdgeMs = 0;
  static unsigned long downAtMs = 0;

  bool pressed = (digitalRead(BUTTON_PIN) == LOW);
  if (pressed == lastPressed) return;
  if (millis() - lastEdgeMs < DEBOUNCE_MS) return;

  lastEdgeMs = millis();
  lastPressed = pressed;

  if (pressed) {
    downAtMs = millis();
    return;
  }

  unsigned long heldMs = millis() - downAtMs;
  if (heldMs < TAP_MAX_MS) {
    onTap();
  } else if (heldMs >= HOLD_MIN_MS) {
    onHold();
  }
  // 500-999ms is a dead zone, discarded on purpose
}

void onTap() {
  if (currentMode == PAUSED) {
    startTransitionTo(AUTO, autoPreset);
  } else if (currentMode == AUTO) {
    startTransitionTo(PAUSED, autoPreset);
  }
  // ignored during BREATHING, cancel that with a hold instead
}

void onHold() {
  if (currentMode == BREATHING_EXERCISE) {
    startTransitionTo(AUTO, autoPreset);
  } else {
    breathCycleCount = 0;
    startTransitionTo(BREATHING_EXERCISE, autoPreset);
  }
}


// ============================================================
// TRANSITION (fade to black, switch, fade back in)
// ============================================================

uint8_t getCurrentValue() {
  if (currentMode == AUTO) {
    const Preset& p = PRESETS[autoPreset];
    return (uint8_t)(p.vMin + (p.vMax - p.vMin) * currentBrightness);
  }
  return (uint8_t)(currentBrightness * 255);  // PAUSED / BREATHING use 0-255 directly
}

void startTransitionTo(Mode newMode, int newPreset) {
  isTransitioning = true;
  transitionStartMs = millis();
  transitionStartValue = getCurrentValue();
  pendingMode = newMode;
  pendingPreset = newPreset;
}

void renderTransition(unsigned long now) {
  unsigned long elapsed = now - transitionStartMs;

  if (elapsed >= FADE_MS) {
    isTransitioning = false;
    currentMode = pendingMode;
    autoPreset  = pendingPreset;
    cycleStartMs = now;
    startNextCycleFromBlack = true;
    if (currentMode == BREATHING_EXERCISE) {
      breathCycleStartMs = now;
    }
    return;
  }

  float t = (float)elapsed / (float)FADE_MS;
  t = 0.5 - 0.5 * cos(t * PI);  // smooth ease, not linear
  uint8_t value = (uint8_t)(transitionStartValue * (1.0 - t));

  uint16_t hue;
  uint8_t  sat;
  if (currentMode == BREATHING_EXERCISE || pendingMode == BREATHING_EXERCISE) {
    hue = BRTH_HUE; sat = BRTH_SAT;
  } else if (currentMode == PAUSED || pendingMode == PAUSED) {
    hue = 0; sat = 0;  // grey, saturation 0 regardless of value
  } else {
    hue = PRESETS[autoPreset].hue; sat = PRESETS[autoPreset].saturation;
  }

  strip.fill(strip.gamma32(strip.ColorHSV(hue, sat, value)));
  strip.show();
  currentBrightness = (float)value / 255.0;
}


// ============================================================
// RENDERING
// ============================================================

void render(unsigned long now) {
  if (isTransitioning) {
    renderTransition(now);
  } else if (currentMode == PAUSED) {
    renderPaused();
  } else if (currentMode == BREATHING_EXERCISE) {
    renderBreathingExercise(now);
  } else {
    renderAmbient(now);
  }
}

void renderAmbient(unsigned long now) {
  const Preset& p = PRESETS[autoPreset];
  unsigned long elapsed = now - cycleStartMs;

  if (elapsed >= p.cycleMs) {
    cycleStartMs = now;
    elapsed = 0;
    startNextCycleFromBlack = false;
  }

  float t = (float)elapsed / (float)p.cycleMs;
  float brightness = 0.5 - 0.5 * cos(t * 2.0 * PI);

  uint8_t value;
  if (startNextCycleFromBlack) {
    // First cycle after a state change rises from true black, not mid-breath
    value = (uint8_t)(p.vMax * brightness);
    if (elapsed >= p.cycleMs / 2) startNextCycleFromBlack = false;
  } else {
    value = (uint8_t)(p.vMin + (p.vMax - p.vMin) * brightness);
  }

  strip.fill(strip.gamma32(strip.ColorHSV(p.hue, p.saturation, value)));
  strip.show();
  currentBrightness = brightness;
}

void renderPaused() {
  // Flat, steady, dim, no animation. Fixed brightness per May 4 design note.
  const float PAUSED_BRIGHTNESS = 0.35;
  uint8_t value = (uint8_t)(255 * PAUSED_BRIGHTNESS);
  strip.fill(strip.gamma32(strip.ColorHSV(0, 0, value)));
  strip.show();
  currentBrightness = PAUSED_BRIGHTNESS;
}

void renderBreathingExercise(unsigned long now) {
  unsigned long elapsed = now - breathCycleStartMs;
  unsigned long totalCycle = INHALE_MS + HOLD_MS + EXHALE_MS;

  const float PEAK  = 1.0;
  const float FLOOR = 0.35;
  float inhaleStart = (breathCycleCount == 0) ? 0.0 : FLOOR;
  float brightness;

  if (elapsed < INHALE_MS) {
    float t = (float)elapsed / (float)INHALE_MS;
    brightness = inhaleStart + (PEAK - inhaleStart) * (0.5 - 0.5 * cos(t * PI));
  } else if (elapsed < INHALE_MS + HOLD_MS) {
    float t = (float)(elapsed - INHALE_MS) / (float)HOLD_MS;
    float wobble = 0.04 * (0.5 - 0.5 * cos(t * 2.0 * PI * 2.0));
    brightness = PEAK - wobble;
  } else if (elapsed < totalCycle) {
    float t = (float)(elapsed - INHALE_MS - HOLD_MS) / (float)EXHALE_MS;
    brightness = FLOOR + (PEAK - FLOOR) * (0.5 + 0.5 * cos(t * PI));
  } else {
    breathCycleCount++;
    breathCycleStartMs = now;

    if (breathCycleCount >= BRTH_CYCLES) {
      startTransitionTo(AUTO, autoPreset);   // done, back to auto
      return;
    }
    brightness = FLOOR;
  }

  uint8_t value = (uint8_t)(255 * brightness);
  strip.fill(strip.gamma32(strip.ColorHSV(BRTH_HUE, BRTH_SAT, value)));
  strip.show();
  currentBrightness = brightness;
}
