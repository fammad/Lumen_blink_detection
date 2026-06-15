"""
mock_visualizer.py - Lumen Dome State Visualizer

Animates a Colored circle to represent the current DomeState.
Used to validate state machine logic and light behavior variations
before doing something with hardware.

"""

import tkinter as tk
import time
import math
from state import DomeState

# Base RGB color per state (full brightness values)
STATE_COLORS = {
    DomeState.CALM:      (255, 220, 140),   # warm yellowish white — ambient lamp feel
    DomeState.ATTENTION: (255, 100,   0),   # clear orange
    DomeState.BREAK:     (220,  20,   0),   # deep red
    DomeState.BREATHING: (  0, 255,  80),   # bright green
    DomeState.PAUSED:    ( 80,  80,  80),   # neutral grey, visible in daylight
}

# Pulse cycle duration in seconds per state
STATE_CYCLE = {
    DomeState.CALM:      10.0,   # slow — spec says ~10s
    DomeState.ATTENTION: 5.0,    # faster — spec says ~5s
    DomeState.BREAK:     8.0,    # slightly slower than ATTENTION
    DomeState.BREATHING: 19.0,   # 4-7-8 cycle total
    DomeState.PAUSED:    0,      # no pulse — steady
}

# Brightness range per state: (min, max)
STATE_BRIGHTNESS = {
    DomeState.CALM:      (0.40, 0.85),   # never fully off — has to read in daylight
    DomeState.ATTENTION: (0.45, 1.00),   # full peak, higher floor than CALM
    DomeState.BREAK:     (0.25, 0.65),   # artifact withdraws — noticeably dimmer than ATTENTION
    DomeState.BREATHING: (0.20, 1.00),   # full range — the exercise needs the contrast
    DomeState.PAUSED:    (0.35, 0.35),   # flat, but visible
}

def get_brightness(state: DomeState) -> float:
    """
    Return current brightness (0.0–1.0) for the given state.
    Sine wave riding on real clock time — consistent tempo regardless of frame rate.
    """
    lo, hi = STATE_BRIGHTNESS[state]
    cycle = STATE_CYCLE[state]

    if cycle == 0:
        return lo   # PAUSED — flat, no animation

    t = time.time()
    # sin() oscillates -1 to 1; map to 0–1, then scale to lo–hi range
    raw = 0.5 + 0.5 * math.sin(2 * math.pi * t / cycle)
    return lo + (hi - lo) * raw

def state_to_color(state: DomeState) -> str:
    """Return tkinter hex color string for current state and time."""
    r_base, g_base, b_base = STATE_COLORS[state]
    brightness = get_brightness(state)

    r = int(r_base * brightness)
    g = int(g_base * brightness)
    b = int(b_base * brightness)

    # Clamp to 0–255 (int rounding can theoretically exceed bounds)
    r = max(0, min(255, r))
    g = max(0, min(255, g))
    b = max(0, min(255, b))

    return f"#{r:02x}{g:02x}{b:02x}"

class MockVisualizer:
    """
    Tkinter window showing dome state as an animated colored circle.
    Call set_state() to change state. Call run() to start the event loop.
    """
    WINDOW_SIZE = 400
    CIRCLE_RADIUS = 120

    def __init__(self):
        self.current_state = DomeState.CALM
        self._build_window()

    def _build_window(self):
        """Create the tkinter window and all widgets."""
        self.root = tk.Tk()
        self.root.title("Lumen — Mock Visualizer")
        self.root.resizable(False, False)

        # Canvas for the circle
        self.canvas = tk.Canvas(
            self.root,
            width=self.WINDOW_SIZE,
            height=self.WINDOW_SIZE,
            bg="#111111"   # dark background — shows the light colors properly
        )
        self.canvas.pack()

        # State label below the circle
        self.label = tk.Label(
            self.root,
            text="CALM",
            font=("Helvetica", 18),
            fg="white",
            bg="#111111"
        )
        self.label.pack(pady=8)

        # One circle object — we'll update its color each frame
        cx = self.WINDOW_SIZE // 2     # center x
        cy = self.WINDOW_SIZE // 2     # center y
        r  = self.CIRCLE_RADIUS

        self.circle = self.canvas.create_oval(
            cx - r, cy - r,
            cx + r, cy + r,
            fill="#0050b4",
            outline=""       # no border
        )

        # Keyboard shortcuts to manually set state — for testing
        self.root.bind("1", lambda e: self.set_state(DomeState.CALM))
        self.root.bind("2", lambda e: self.set_state(DomeState.ATTENTION))
        self.root.bind("3", lambda e: self.set_state(DomeState.BREAK))
        self.root.bind("4", lambda e: self.set_state(DomeState.BREATHING))
        self.root.bind("5", lambda e: self.set_state(DomeState.PAUSED))


    def set_state(self, state: DomeState):
        """Change the current dome state."""
        self.current_state = state
        self.label.config(text=state.name)

    def _update_frame(self):
        """Called every 50ms. Recolors the circle and reschedules itself."""
        color = state_to_color(self.current_state)
        self.canvas.itemconfig(self.circle, fill=color)
        self.root.after(50, self._update_frame)   # schedule next frame

    def run(self):
        """Start the animation loop and open the window."""
        self._update_frame()    # kick off the loop
        self.root.mainloop()    # blocks here until window is closed

if __name__ == "__main__":
    viz = MockVisualizer()
    viz.run()