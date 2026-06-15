"""
baseline.py — Lumen rolling baseline engine.

Provides the BaselineEngine class, which maintains a rolling reference
blink rate for the current user. The reference is the arithmetic mean of
the last WINDOW samples, clamped to a literature-derived floor (Rosenfield
2011). The deque is pre-filled with a literature prior so the reference is
meaningful from the first sample onward.
"""

from collections import deque

FLOOR = 7
PRIOR = 15
WINDOW = 30

class BaselineEngine:
    def __init__ (self):
        self.samples = deque([PRIOR] * WINDOW, maxlen=WINDOW)
        self.samples_collected = 0
        self.current_rate = PRIOR

    def add_sample(self, last_window_blink):
        """Record a new measurement. Called every minute (real) or every second (quick-cal)."""
        self.samples.append(last_window_blink)
        self.samples_collected = min(self.samples_collected +1, WINDOW)
        self.current_rate = last_window_blink        

    def get_state(self):
        """Return the state of the baseline for risk score"""
        personal_baseline = sum(self.samples) / WINDOW
        reference = max(personal_baseline, FLOOR)
        floor_active = reference > personal_baseline

        return {
            "reference" : reference,
            "personal_baseline" : personal_baseline,
            "floor_active" : floor_active,
            "current_rate" : self.current_rate,
            "samples_collected" : self.samples_collected,
        }
    

if __name__ == "__main__":
    # --- Scenario 1: fresh start ---
    engine = BaselineEngine()
    print(f"Fresh start: {engine.get_state()}")

    # --- Scenario 2: healthy user, 30 samples around 15 ---
    healthy_samples = [5, 16, 15, 14, 16, 15, 15, 14, 16, 15] * 3
    for s in healthy_samples:
        engine.add_sample(s)
    print(f"After healthy session: {engine.get_state()}")

    # --- Scenario 3: strained user, 30 more samples around 5 ---
    strained_samples = [4, 5, 6, 10, 4, 5, 6, 5, 4, 15] * 3
    for s in strained_samples:
        engine.add_sample(s)
    print(f"After strained session: {engine.get_state()}")
