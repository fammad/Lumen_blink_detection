"""
This class answer to the questions regarding to how concerned should the dome be right now?
Consumes baseline state from BaselineEngine. Does NOT own break
detection policy, the main loop calls mark_break() when a break
condition fires
"""
import time

FOCUS_SATURATE_MIN = 20   # minutes before focus_risk maxes out
WEIGHTS = (0.5, 0.5)      # (blink_weight, focus_weight)

CALM_MAX    = 0.3    # risk_score below this → CALM
ATTENTION_MAX = 0.6  # risk_score below this → ATTENTION, above → BREAK


class RiskEngine:
    """Stateful risk scorer. Tracks time since last break."""

    def __init__(self, start_time):

        self.last_break_time = start_time

    def mark_break(self, now):
        """Reset the focus timer. Called by main loop when break fires."""
        self.last_break_time = now

    def get_risk(self, baseline_state, now):
        """Compute risk score from baseline state and elapsed focus time."""
        
        minutes_without_break = (now - self.last_break_time)/60
        reference = baseline_state["reference"]
        current_rate = baseline_state["current_rate"]
        blink_risk   = max(0.0, (reference - current_rate) / reference)

        focus_risk = min(1.0, minutes_without_break / FOCUS_SATURATE_MIN)

        blink_weight, focus_weight = WEIGHTS
        risk_score = blink_weight * blink_risk + focus_weight * focus_risk
   
        if risk_score < CALM_MAX:
            recommended_state = "CALM"
        elif risk_score < ATTENTION_MAX:
            recommended_state = "ATTENTION"
        else:
            recommended_state = "BREAK"


        return {
        "risk_score":           risk_score,
        "blink_risk":           blink_risk,
        "focus_risk":           focus_risk,
        "minutes_without_break": minutes_without_break,
        "recommended_state":    recommended_state,
        "reference":            reference,
        "current_rate":         current_rate,
        "floor_active":         baseline_state["floor_active"],
        "samples_collected":    baseline_state["samples_collected"],
        }



    
if __name__ == "__main__":

    # Shared baseline state — healthy reference
    healthy_state = {
        "reference": 15.0,
        "current_rate": 15.0,
        "floor_active": False,
        "samples_collected": 30,
        "personal_baseline": 15.0,
    }

    strained_state = {
        "reference": 15.0,
        "current_rate": 5.0,
        "floor_active": False,
        "samples_collected": 30,
        "personal_baseline": 15.0,
    }

    t0 = 0.0  # fake session start

    # Scenario 1: fresh, healthy
    engine = RiskEngine(start_time=t0)
    print(f"Fresh healthy:       {engine.get_risk(healthy_state, now=t0)}")

    # Scenario 2: strained blink, 5 min elapsed
    print(f"Strained 5min:       {engine.get_risk(strained_state, now=t0 + 300)}")

    # Scenario 3: healthy blink, 60 min elapsed
    print(f"Healthy 60min:       {engine.get_risk(healthy_state, now=t0 + 3600)}")

    # Scenario 4: both strained, 30 min elapsed
    print(f"Strained 30min:      {engine.get_risk(strained_state, now=t0 + 1800)}")

    # Scenario 5: mark_break resets timer
    engine.mark_break(now=t0 + 1800)
    print(f"After break (t=30):  {engine.get_risk(strained_state, now=t0 + 1800)}")

