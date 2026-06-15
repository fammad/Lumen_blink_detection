"""
state.py — Lumen dome state definitions.

All valid dome states.
Import DomeState into any module that needs to read or set state.
"""

from enum import Enum


class DomeState(Enum):
    CALM      = 1   # risk_score < 0.3 — slow blue breathing
    ATTENTION = 2   # 0.3 ≤ risk_score < 0.6 — faster amber breathing
    BREAK     = 3   # risk_score ≥ 0.6 — dim red, artifact withdraws
    BREATHING = 4   # user initiated hold gesture — 4-7-8 exercise
    PAUSED    = 5   # user initiated tap gesture — sensing stopped


if __name__ == "__main__":
    print("All states:")
    for s in DomeState:
        print(f"  {s.value}: {s.name}")

    print("\nComparison test:")
    current = DomeState.CALM
    print(f"  current is CALM: {current is DomeState.CALM}")
    print(f"  current is BREAK: {current is DomeState.BREAK}")