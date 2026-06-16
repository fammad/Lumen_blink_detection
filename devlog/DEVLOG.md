# Lumen — Dev Log

Running build log kept during development, published as written — dated entries, including dead ends and reversed decisions, not cleaned up after the fact.

**Project:** Lumen (tangible object for negotiated screen-work interruption)
**Repo:** github.com/fammad/lumen
**Author:** Fuad Mammadov, KTH IMT MSc

---

## April 5 — Concept

Started thinking about Lumen as a physical object. Brainstormed what the interaction should feel like, what problem it was actually solving, and whether it was worth building at all. No code yet.

## April 10 — Logic and structure

Started investigating the detection logic. Imported variables, mapped out what the system needed to track across frames. Still no working code — mostly understanding what MediaPipe gives you and what you have to compute yourself.

## April 15 — Environment, repo, first working detection

Set up the venv environment, created the GitHub repo, added dependencies. Python 3.12 pinned, mediapipe fixed at 0.10.14 because 3.13 breaks the `mp.solutions` API.

Built `test_facemesh.py` first to confirm MediaPipe face mesh was actually running before touching eye-specific logic. Once that worked, moved to `eye_landmarks.py` — isolated the 6 landmark indices per eye and drew them on the webcam feed. Then wrote `blink_detector.py` with the EAR calculation. By end of day, EAR was printing live to screen.

Hardware is still pending. Everything so far is software only.

## April 21 — Blink counter

Added blink event detection on top of the EAR values. Took three iterations.

First version triggered on average EAR across both eyes. Head turns caused false counts because the far eye's landmarks compress at angle and EAR drops without a real blink.

Second version required both eyes to be below threshold simultaneously. Fixed head-turn artifacts and filtered winks.

Third version added a minimum open duration — 3 consecutive above-threshold frames required before a reopen is confirmed. Squinting was oscillating below and above threshold repeatedly and counting each recovery as a blink. This stopped it.

Result: 10 deliberate blinks, count showed 10. Open-eye EAR baseline is 0.33 in evening home lighting. Threshold is set at 0.21. That gap will likely need re-tuning under conference fluorescents in Vaasa.

ESP32-S3 not yet ordered. No hardware built.

## April 22 - Blink Rate per 60 second.

Added blink counting functionality to the code that can be used to count how many blink occured in 60 seconds.

First created new constants(how many second has to count) and variables (dequeu four double ended queue). The code append every time it sees new blink. If the blink is out of given WINDOW_SECOND it drops thhe frist blink_times[0] one and add this one if this code true while blink_times and now - blink_times[0] > WINDOW_SECONDS

Result: 2 minute user test to count manual eye blink with the system. It was accurate. But I realized my blink rate is around 5-9 per minute which is not typical.

## April 23 — Range and lighting test

Tested blink detection accuracy across distance and lighting conditions.

MacBook Pro built-in camera, 1920×1080 at 60 FPS.

Low light: ~99% accurate up to 120 cm. Beyond that, landmark confidence 
drops and EAR values become unstable.

Normal / daylight: ~99% accurate up to 150 cm. Same degradation pattern 
past that threshold — not a gradual drop, more like a cliff.

This matters for the NordiCHI demo: attendees will be sitting ~60–80 cm 
from the screen. Both lighting conditions cover that range comfortably. 
The threshold cliff past 150 cm is not a concern for the demo setup, but 
I'll note the range limit in the abstract's limitations paragraph.

EAR threshold is still 0.21. Haven't re-tuned for conference fluorescents 
yet — that's the Sprint 4 lighting test.


## April 28 — Rolling baseline engine

Built `BaselineEngine` class - owns "what's the healthy blink rate reference for this user right now?" Returns reference, personal_baseline, floor_active, current_rate, samples_collected via get_state().

Hybrid design: deque pre-filled with PRIOR=15 (Rosenfield healthy at-rest rate) so the baseline is meaningful from sample 1, no warm-up dead time. Reference = max(personal_baseline, FLOOR) where FLOOR=7 (Rosenfield strain threshold). The floor catches drift — without it, sustained strain pulls the rolling mean down with the user, and the system silently agrees with the deteriorating state instead of pushing back.

Considered session-scale blending of calibration baseline with rolling rate. Rejected — any weighted average with a low recent rate pulls reference down, reintroducing the drift bug. Escalation over time belongs to the focus-clock in Task 2.2, not the baseline.

Smoke test (3 scenarios):
- Fresh start: reference=15.0, samples_collected=0 (deque full of priors)
- 30 healthy samples (~15): reference=15.0, floor_active=False
- 30 strained samples (~5): reference=7, personal_baseline=4.9, floor_active=True ← floor catching drift

What I learned: deque(iterable, maxlen=N) is the right structure for FIFO rolling windows. Pre-filling with a literature prior is Bayesian-style initialization. Always trace mechanically (sum=147, /30=4.9) before reaching for narrative ("the system decided"). And \n is a newline; /n is two characters.


## April 29 — Risk Scoring and Tweak

Some ideas for risk score:
20 minutes is when time-pressure alone maxes out its contribution to the risk score. After 20 minutes of continuous focus, the clock has nothing more to say — but the clock alone never crosses the BREAK threshold. Strain in the blink rate must also be present. This separates duration from strain: long focus is concerning, but only concerning enough to escalate the dome when accompanied by physiological evidence.



## April 30 Risk scoring engine

Built `RiskEngine` class in `risk_engine.py` — owns "how concerned 
should the dome be right now?" Consumes baseline state dict from 
BaselineEngine. Single stored attribute: `last_break_time`. 
Everything else computed fresh per call.

Formula:
- blink_risk = max(0, (reference - current_rate) / reference)
- focus_risk = min(1.0, minutes_without_break / 20)
- risk_score = 0.5 * blink_risk + 0.5 * focus_risk
- CALM < 0.3 / ATTENTION < 0.6 / BREAK ≥ 0.6

Key design decisions:
- FOCUS_SATURATE_MIN = 20: motivated by AOA 20-20-20 rule and 
  work-block research (Cirillo 2006, Mark 2008). Tunable constant,
  not a derived value.
- Focus alone caps at 0.5 risk (0.5 weight). Cannot trigger BREAK 
  without blink strain also present. Time is a concern, not a sentence.
- mark_break() resets focus clock only. Blink strain persists across 
  breaks — intentional. A break addresses time, not physiology.
- Time injected as parameter (not time.time() internally) — 
  enables testing without waiting real seconds.

Smoke test (5 scenarios):
- Fresh healthy: score=0.0, CALM ✓
- Strained 5min: score=0.458, ATTENTION ✓  
- Healthy 60min: score=0.5, ATTENTION ✓ (clock alone never triggers BREAK)
- Strained 30min: score=0.833, BREAK ✓
- After mark_break: focus_risk=0.0, still ATTENTION (blink strain 
  persists) ✓

Considered resetting baseline after breaks by injecting healthy 
values into deque. Rejected — same drift bug from opposite direction. 
If user's blink rate is genuinely 5/min post-break, showing CALM 
would be dishonest. Baseline reflects reality; it doesn't reset 
to optimism.



## May 1 - State machine and mock visualizer

Added state.py with DomeState enum: CALM, ATTENTION, BREAK, BREATHING, PAUSED. 
Single source of truth for dome states — every downstream module will import 
from here instead of comparing strings. Pre-filled integers 1–5, standard 
library Enum, no dependencies.

Built mock_visualizer.py — tkinter window with animated circle driven by 
real-clock sine wave. Brightness and cycle duration defined per state in 
three dicts (STATE_COLORS, STATE_CYCLE, STATE_BRIGHTNESS). Keyboard bindings 
1–5 for manual state switching. Two bugs found and fixed: tkinter not 
bundled with Homebrew Python 3.12 (fixed with brew install python-tk@3.12), 
and three methods accidentally dedented out of MockVisualizer class 
(indentation fix). 

Initial color palette was too saturated for daylight use — conference 
fluorescents and desk ambient light won't produce the dark-room contrast 
the original values assumed. Retuned to warm yellowish-white for CALM, 
clear orange for ATTENTION, deep red for BREAK, bright green for BREATHING. 
Brightness floors raised across all states so colors remain readable in 
ambient light. BREAK amplitude compressed (0.25–0.65) to preserve the 
withdrawal behavior against McFarlane framing.


## May 2 — F1 validation

Ran blink detection accuracy test across 6 conditions: three distances 
(1m, 1.5m, 2m) in direct sunlight, one movement stress test at 1m, 
and two distances under table lamp only.

Results: F1 ≥ 0.90 for all conditions within the demo operating envelope 
(≤1.5m). Sharp degradation at 2m in low light (F1=0.57) — landmark 
confidence drops below reliable tracking threshold at that distance. 
No re-tune needed; EAR threshold stays at 0.21.

Demo setup uses 60–80cm distance. All tested conditions at that range 
perform at F1 ≥ 0.92. Head-turn stress test at 1m returned F1=0.92; 
some false positives from landmark compression may be present in that 
figure but were not counted separately.

Limitation documented in README. Will report F1=0.92 (head-turn condition, 
most conservative passing result) as the headline validation figure in the 
abstract — honest and adversarial rather than cherry-picking the 1.0 result.

## May 4 — BREATHING and PAUSED States Implemented

Added BREATHING (value 4) and PAUSED (value 5) to the DomeState enum in
state.py. Both were already specified in the interaction design but not
previously logged as implemented.

BREATHING — user-initiated 4-7-8 breathing exercise. Triggered by a
hold gesture. Full brightness range (0.20–1.00) to maximise contrast for
the inhale/exhale cue. Bright green (#00ff50).

PAUSED — user-initiated tap gesture stops sensing entirely. Flat steady
grey, no animation pulse. Cycle duration = 0 (get_brightness() returns
the floor constant, no sine computation).

Both states have full color, brightness envelope, and cycle definitions
in mock_visualizer.py. BREATHING cycle = 19.0s (4 + 7 + 8 = 19, exact
4-7-8 pattern). PAUSED brightness is fixed at 0.35 (visible in ambient
light, clearly dimmer than active states).

Animation is driven by real-clock time.time() inside get_brightness(),
so tempo is frame-rate independent — the circle stays in sync regardless
of how fast tkinter rerenders.


## May 7-10 — Integration Loop: main.py

Wired all modules together into a single live pipeline: webcam → blink
detection → BaselineEngine → RiskEngine → state badge + console log.

main.py is now the single entry point for the full system. All previous
modules (blink_detector, baseline, risk_engine, state) are imported here.

Key design decisions:

- FACE_LOST_THRESHOLD = 30.0s — if no face detected for 30+ continuous
  seconds, mark_break() is called every frame (idempotent). Focus clock
  stays at 0 throughout the absence. Baseline receives no new samples
  while face is absent; deque preserves its last known state and picks
  up where it left off when face returns.

- DEMO_MODE toggle (d key) — switches between 1s baseline sampling
  (settles in ~30s for demos) and 60s real-mode sampling (settles in
  ~30 min). BASELINE_INTERVAL is set at startup from this flag.

- Override system (keys 1/2/3/0) — user can force CALM / ATTENTION /
  BREAK regardless of sensor state. State badge displays "STATE [OVR]"
  when active. Key 0 clears override and returns to auto.

- NO_SIGNAL state — when face is absent the badge shows "NO SIGNAL" in
  grey instead of displaying a stale auto state. Does not crash.

- Glass panel HUD overlay — draw_glass_panel() renders semi-transparent
  alpha-blended rounded rectangles (55% opacity) over the camera feed.
  Left panel: EAR, blink count, rolling rate. Right panel: risk score,
  reference blink rate (floor-flagged with *), focus elapsed time,
  demo/real mode, and session elapsed seconds (T+Xs).

- State change logging — console output fires only on transitions, not
  every frame. Risk breakdown (risk=X, blink=X, focus=X) is appended to
  auto transitions so the log is a readable trace of what the engine
  decided and why.

- Full session reset (r key) — resets blink counter, blink_times deque,
  BaselineEngine, RiskEngine, focus timer, override, and session clock
  in a single keystroke. Useful between user research participants.


  ## May 13 — Arduino Hardware Session with Yuting + Breathing Pattern Testing

First physical hardware session. Tested the NeoPixel dome with Yuting.

Hardware (locked from this session):
  NeoPixel ring DI → GPIO 5
  Button           → GPIO 4 (INPUT_PULLUP, other leg to GND)
  Brightness       = 150
  Color order      = NEO_GRB

Breathing pattern decisions made during session:

- CALM: warm white (HSV hue 6500, sat 90). 5s cycle for demo (will
  change to 8s for real use). Feels natural, non-intrusive. 10-second
  interval confirmed as the right cadence — doesn't compete with focus.

- ATTENTION: amber/orange (hue 5000, sat 255). Faster pace (4s cycle)
  to signal increased urgency. White was also considered but orange
  reads more distinctly as "pay attention."

- BREAK: deep red (hue 0, sat 255). 4s cycle. Amplitude compressed
  (vMin=130, vMax=220) so the dome visibly withdraws — artifact behavior
  per McFarlane framing. Does not pulse as brightly as ATTENTION.

- BREATHING exercise: soft green (hue 22000, sat 200). 4-7-8 pattern
  (inhale 4s, hold 7s, exhale 8s). 2 full cycles = ~38s total. Floor
  brightness 35% (always visibly lit — never goes dark during hold).
  Subtle wobble during hold phase signals "stay here" without looking
  frozen.

Button interaction:
  Short press  (< 500ms):   cycle CALM → ATTENTION → BREAK → CALM
  Hold         (≥ 1000ms):  start / cancel breathing exercise
  Dead zone    (500–999ms): discarded — ambiguous gesture

Serial commands (115200 baud) for testing: c / a / b / x for states,
0–3 to switch CALM breathing variation.

CALM breathing style variations (for subtle demo testing):
  0 — SYMMETRIC    (smooth cosine, equal inhale/exhale) ← default
  1 — ASYMMETRIC   (fast inhale 1/3, slow exhale 2/3)
  2 — RANDOM_PEAKS (peak brightness varies 60–100% per cycle)
  3 — JITTER       (cycle duration varies ± 1.5s)

Symmetric felt most natural in the room. Asymmetric was noticeable but
not distracting. Jitter was interesting but potentially anxiety-inducing
under strain — not recommended as default.

Firmware: lumen_demo.ino (Arduino IDE). Adafruit_NeoPixel library.
ESP32-S3, GPIO 4 + 5.



## May 15 — User Testing Session (Future Update)

First formal user research session with external participants.

Session structure:
1. Pre-use questionnaire — attitudes toward negotiated interruption,
   notification habits, and ambient computing awareness.
2. Live demo with the physical Lumen artifact — participants interact
   with the NeoPixel dome directly, cycling through CALM / ATTENTION /
   BREAK states via button tap and triggering the BREATHING exercise
   via hold gesture.
3. Pattern preference test — participants experience each CALM breathing
   variation (SYMMETRIC, ASYMMETRIC, RANDOM_PEAKS, JITTER) and rate them.
4. Post-use debrief — open questions on perceived intrusiveness,
   naturalness of the light behavior, and willingness to negotiate
   break-taking with a physical object vs. a screen notification.

6 user came and we had 1 hour, 30 minutes critic session.

Ideas from users: 
- Make circular object and platform sits on individual so if there's a brake user can take it maybe it can be interaction.
- Lighting intensitiy should change based on the envrionment brightness. We can add some light sensor and compensate if it is intense or vise versa.
- Most of the user said orange, red or different color and fast pase breathing exercise comibine can be extra noticable. Everynone choose one element version the ATTENTION phase. Most said light intensity like 5 second change is okay without color.
- breathing exerice works and it is not obligatory to do in front of camera so nice that you can do brake 
- Some user said for privacy they would prefer to disable tracking, sometimes if they want to watch movie or somethign they had to have intention to make a brake.
- One user said it feels like a living organism that sits on the table
- Everyone preffered syncronous breathing patter becasue others felt unnatural.  It feels like us breakthing or something (our dynasaurus egg) annoyed that you dont make a brake.
- facial expressiveness other than eye blinks can be indication of tiredness alongside changing position more relaxed one, distraction etc.
- most of user wanted to interact with putting their hand on it for breathing exercise or squizze to say not to notification and ignore
- it has to have op;tion to defer the red ACTION part or it has not big difference between notification pop ups and phytsical form. 


## July 5, Closed the sensor to actuator loop

Software and hardware had been two separate demos until now. main.py computed
the risk score and only showed it in the OpenCV window. lumen_demo.ino only
responded to manual serial keystrokes typed while watching that window. All
hardware sessions up to May 15 ran this way, with me matching the light to
the screen by hand.

Found lumen_demo.ino didn't actually compile as last committed. Leftover
scratch text had ended up outside the comment blocks and broke the build.
Also missing: the ATTENTION/amber preset (only CALM and BREAK existed), and
any code reading the button on GPIO 4, despite that pin being locked back in
the May 13 session.

Rewrote the firmware: three presets (CALM, ATTENTION, BREAK) with the hue,
saturation and cycle values from May 13, a serial protocol of single letters
(C/A/B) instead of the old video-shoot digit commands, and a debounced button
handler. Tap toggles PAUSED (flat grey, fixed 0.35 brightness). Hold starts
the breathing exercise, which now ends itself after 2 cycles and returns to
the last auto state instead of running forever. This replaces the early
May 13 button behavior (short tap cycling CALM to ATTENTION to BREAK), which
only existed because there was no automatic pipeline yet to drive the states.

Added the other half in main.py: opens a serial port at 115200 baud if
SERIAL_PORT is set, sends C/A/B whenever the displayed state changes, and
runs exactly as before if no dome is connected.

Flashed and tested on the real ESP32-S3. All three states, tap-to-pause, and
hold-to-breathe worked as designed. First time the blink signal has driven
the dome without me in the loop.
