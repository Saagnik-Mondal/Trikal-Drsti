from dataclasses import dataclass
from typing import List, Optional
from .core import ViewConclusion

@dataclass
class Conflict:
    """Represents a disagreement between two views."""
    views_involved: List[str]
    description: str
    severity: float # 0.0 to 1.0

@dataclass
class FinalDecision:
    """The resolved output from the system."""
    primary_conclusion: ViewConclusion
    conflicts: List[Conflict]
    explanation: str

class ConflictDetector:
    """Detects logical contradictions between temporal views."""
    
    def detect(self, conclusions: List[ViewConclusion]) -> List[Conflict]:
        conflicts = []
        
        # Map by timescale
        by_scale = {c.time_scale: c for c in conclusions}
        
        short = by_scale.get("Short")
        mid = by_scale.get("Mid")
        long_term = by_scale.get("Long")

        # 1. Trend Conflict: Short vs Mid
        if short and mid:
            if (short.sentiment == "RISING" and mid.sentiment == "FALLING") or \
               (short.sentiment == "FALLING" and mid.sentiment == "RISING"):
                conflicts.append(Conflict(
                    views_involved=["Short", "Mid"],
                    description=f"Short term direction ({short.sentiment}) opposes Mid term trend ({mid.sentiment}).",
                    severity=0.6
                ))

        # 2. Stability Conflict: Volatility vs Long Term Stability
        if short and long_term:
            if short.sentiment == "VOLATILE" and long_term.sentiment == "BASELINE":
                conflicts.append(Conflict(
                    views_involved=["Short", "Long"],
                    description="Short term volatility is detected within a stable long-term baseline.",
                    severity=0.3
                ))

        # 3. Drift Conflict: Mid Trend vs Long Term Deviation
        if mid and long_term:
            if mid.sentiment == "RISING" and long_term.sentiment == "OVEREXTENDED_HIGH":
                conflicts.append(Conflict(
                    views_involved=["Mid", "Long"],
                    description="Mid term trend is pushing further into overextended territory.",
                    severity=0.8
                ))
        
        return conflicts

class ResolutionEngine:
    """Decides which view to trust based on heuristic dominance rules."""
    
    def resolve(self, conclusions: List[ViewConclusion], conflicts: List[Conflict]) -> FinalDecision:
        by_scale = {c.time_scale: c for c in conclusions}
        short = by_scale.get("Short")
        mid = by_scale.get("Mid")
        long_term = by_scale.get("Long")
        
        # Default: Trust Mid-term (Trend) usually assumes the best signal-to-noise
        dominant = mid
        explanation = "Following local trend as the default reliable signal."

        # Rule 1: Safety Override (Short-term Crash requires immediate attention)
        if short and short.sentiment == "CRASH":
            dominant = short
            explanation = "URGENT: Short-term crash detected. Immediate volatility overrides trends."
        
        # Rule 2: Mean Reversion (If Long-term is extremely overextended, bet against the trend)
        elif long_term and long_term.sentiment in ["OVEREXTENDED_HIGH", "OVEREXTENDED_LOW"] and mid:
            # Check if Mid is still pushing in the wrong direction
            if (long_term.sentiment == "OVEREXTENDED_HIGH" and mid.sentiment == "RISING") or \
               (long_term.sentiment == "OVEREXTENDED_LOW" and mid.sentiment == "FALLING"):
                dominant = long_term
                explanation = "CAUTION: Market is structurally overextended. Expecting reversion despite local trend."
        
        # Rule 3: Ignore Noise (If Short is Volatile but Mid/Long are stable)
        elif short and short.sentiment == "VOLATILE":
            if mid and mid.confidence > 0.5:
                dominant = mid
                explanation = "Ignoring short-term volatility in favor of established mid-term trend."
            else:
                dominant = short
                explanation = "High uncertainty. Volatility is the only clear signal."

        # Fallback if Mid wasn't available
        if not dominant:
            dominant = long_term if long_term else short

        return FinalDecision(
            primary_conclusion=dominant,
            conflicts=conflicts,
            explanation=explanation
        )
