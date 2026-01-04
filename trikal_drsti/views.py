from typing import List
import statistics
from .core import TemporalView, Event, ViewConclusion

class ShortTermView(TemporalView):
    """Analyzes immediate volatility and noise (Window: ~5-10 events)."""
    
    def __init__(self, name="ShortTerm", window_size=10):
        super().__init__(name, window_size)

    def analyze(self) -> ViewConclusion:
        if len(self.history) < 2:
            return ViewConclusion(self.name, "Short", "INSUFFICIENT_DATA", 0.0, "Not enough data points.", [])

        recent_events = self.history[-self.window_size:]
        values = [e.value for e in recent_events]
        
        # Calculate rate of change (derivative approximation)
        start_val = values[0]
        end_val = values[-1]
        pct_change = (end_val - start_val) / (start_val + 1e-9)
        
        # Calculate volatility (standard deviation)
        if len(values) > 1:
            volatility = statistics.stdev(values)
        else:
            volatility = 0.0

        # Heuristic Logic
        sentiment = "STABLE"
        confidence = 0.5
        reasoning = []

        if volatility > 2.0: # Arbitrary threshold for this dataset scale
            sentiment = "VOLATILE"
            confidence = 0.8
            reasoning.append(f"High volatility (stdev={volatility:.2f})")
        elif abs(pct_change) > 0.05: # 5% swing in short window
            sentiment = "SPIKE" if pct_change > 0 else "CRASH"
            confidence = 0.9
            reasoning.append(f"Rapid price movement ({pct_change*100:.1f}%)")
        else:
            reasoning.append(f"Low volatility (stdev={volatility:.2f})")

        return ViewConclusion(
            view_name=self.name,
            time_scale="Short",
            sentiment=sentiment,
            confidence=confidence,
            reasoning="; ".join(reasoning),
            supporting_events=recent_events
        )


class MidTermView(TemporalView):
    """Analyzes local trends (Window: ~20-50 events)."""

    def __init__(self, name="MidTerm", window_size=30):
        super().__init__(name, window_size)

    def analyze(self) -> ViewConclusion:
        if len(self.history) < self.window_size:
            return ViewConclusion(self.name, "Mid", "INSUFFICIENT_DATA", 0.0, "Building trend history.", [])

        # Simple Moving Average (SMA)
        relevant_history = self.history[-self.window_size:]
        values = [e.value for e in relevant_history]
        sma = sum(values) / len(values)
        current_price = values[-1]
        
        # Linear Regression Slope (simple approximation: compare first half avg vs second half avg)
        mid_point = len(values) // 2
        first_half = values[:mid_point]
        second_half = values[mid_point:]
        avg1 = sum(first_half) / len(first_half)
        avg2 = sum(second_half) / len(second_half)
        
        slope_sentiment = "FLAT"
        if avg2 > avg1 * 1.02:
            slope_sentiment = "RISING"
        elif avg2 < avg1 * 0.98:
            slope_sentiment = "FALLING"

        reasoning = f"SMA is {sma:.2f}. Trend appears {slope_sentiment}."
        
        # Confidence boosts if current price aligns with trend
        confidence = 0.6
        if slope_sentiment == "RISING" and current_price > sma:
            confidence = 0.9
            reasoning += " Price above SMA confirms uptrend."
        elif slope_sentiment == "FALLING" and current_price < sma:
            confidence = 0.9
            reasoning += " Price below SMA confirms downtrend."
        elif slope_sentiment == "RISING" and current_price < sma:
            reasoning += " Price dip below SMA suggests potential reversal."
            confidence = 0.4 # Conflicting signal

        return ViewConclusion(
            view_name=self.name,
            time_scale="Mid",
            sentiment=slope_sentiment,
            confidence=confidence,
            reasoning=reasoning,
            supporting_events=relevant_history
        )


class LongTermView(TemporalView):
    """Analyzes structural drift and accumulation (Window: ~100+ events)."""

    def __init__(self, name="LongTerm", window_size=100):
        super().__init__(name, window_size)

    def analyze(self) -> ViewConclusion:
        if len(self.history) < self.window_size // 2:
             return ViewConclusion(self.name, "Long", "INSUFFICIENT_DATA", 0.0, "Need more history for structure.", [])

        # We look at the entire AVAILABLE history for "cumulative" perspective, 
        # bounded by the view's max history limit from base class
        values = [e.value for e in self.history]
        overall_mean = sum(values) / len(values)
        current_val = values[-1]
        
        # Determine "Regime"
        # Are we significantly deviated from the mean?
        deviation = current_val - overall_mean
        
        sentiment = "BASELINE"
        if deviation > 10.0: # Significant deviation up
            sentiment = "OVEREXTENDED_HIGH"
        elif deviation < -10.0:
            sentiment = "OVEREXTENDED_LOW"
        
        reasoning = f"Long-term mean is {overall_mean:.2f}. Current deviation: {deviation:.2f}."
        
        return ViewConclusion(
            view_name=self.name,
            time_scale="Long",
            sentiment=sentiment,
            confidence=0.7, # Long term is usually "slower" to be wrong
            reasoning=reasoning,
            supporting_events=[self.history[0], self.history[-1]] # Just bookends for reference
        )
