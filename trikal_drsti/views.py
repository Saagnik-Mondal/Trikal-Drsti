from typing import List
import statistics
import math
from .core import TemporalView, Event, ViewConclusion, Sentiment, ViewConfig

class ShortTermView(TemporalView):
    """Analyzes immediate volatility and noise using Z-scores."""
    
    def __init__(self, name="ShortTerm", config: ViewConfig = None):
        if config is None:
            config = ViewConfig(window_size=10, z_threshold=1.5, slope_threshold=0.02, weight=0.5)
        super().__init__(name, config)

    def analyze(self) -> ViewConclusion:
        sentiment = self.get_conclusion()
        confidence = self.get_confidence()
        
        events = self.history[-self.config.window_size:]
        val = events[-1].value if events else 0
        
        reasoning = f"Sentiment: {sentiment.value}. Confidence: {confidence:.2f}."
        if sentiment in [Sentiment.SPIKE, Sentiment.CRASH]:
            reasoning += f" Value {val:.2f} exceeds Z-score threshold {self.config.z_threshold}."
        elif sentiment == Sentiment.VOLATILE:
            reasoning += f" High variance detected."
        
        return ViewConclusion(
            view_name=self.name,
            time_scale="Short",
            sentiment=sentiment,
            confidence=confidence,
            reasoning=reasoning,
            supporting_events=events
        )

    def get_conclusion(self) -> Sentiment:
        if len(self.history) < self.config.window_size:
            return Sentiment.STABLE # Default

        window = self.history[-self.config.window_size:]
        values = [e.value for e in window]
        
        if len(values) < 2: return Sentiment.STABLE

        mean = statistics.mean(values[:-1]) # Mean of previous N-1
        stdev = statistics.stdev(values[:-1]) if len(values) > 2 else 1.0
        current_val = values[-1]
        
        if stdev == 0: stdev = 1e-9 # Avoid div by zero

        z_score = (current_val - mean) / stdev

        if z_score > self.config.z_threshold:
            return Sentiment.SPIKE
        elif z_score < -self.config.z_threshold:
            return Sentiment.CRASH
        
        # Volatility check
        # Normalize volatility relative to mean (CV) or absolute threshold?
        # For generic data, CV (coef of variation) is safer but traffic has 0 mean sometimes.
        # We'll use raw stdev trend. If stdev is huge compared to recent past?
        # Simpler: If recent variance is high.
        # For now, let's stick to STABLE if not SPIKE/CRASH, unless we add explicit Volatility logic later.
        
        return Sentiment.STABLE

    def get_confidence(self) -> float:
        # Confidence is high if we have enough data and signal is clear
        if len(self.history) < 3:
            return 0.3
        
        # Even for stable data, return higher base confidence
        window = self.history[-self.config.window_size:]
        values = [e.value for e in window]
        if len(values) < 2: return 0.3
        
        mean = statistics.mean(values[:-1])
        stdev = statistics.stdev(values[:-1]) if len(values) > 2 else 0.1
        current_val = values[-1]
        if stdev == 0: stdev = 1e-9
        
        z_score = abs((current_val - mean) / stdev)
        
        # Improved confidence: higher baseline for all signals
        # Z < 0.5 -> 0.6 (stable with confidence)
        # Z = 1.0 -> 0.7
        # Z = 1.5 -> 0.85
        # Z = 3.0 -> 0.95
        
        if z_score < 0.5:
            return 0.6  # Higher baseline for stable signals
        elif z_score < 1.0:
            return 0.65
        elif z_score < 1.5:
            return 0.75
        else:
            # Exponential growth for strong signals
            conf = 0.75 + (1.0 - 0.75) * (1.0 - math.exp(-0.5 * (z_score - 1.5)))
            return min(max(conf, 0.0), 1.0)


class MidTermView(TemporalView):
    """Analyzes local trends using Linear Regression Slope."""

    def __init__(self, name="MidTerm", config: ViewConfig = None):
        if config is None:
            config = ViewConfig(window_size=30, slope_threshold=0.001, weight=1.0)
        super().__init__(name, config)

    def analyze(self) -> ViewConclusion:
        sentiment = self.get_conclusion()
        confidence = self.get_confidence()
        reasoning = f"Trend: {sentiment.value}. Conf: {confidence:.2f}."
        
        return ViewConclusion(
            view_name=self.name,
            time_scale="Mid",
            sentiment=sentiment,
            confidence=confidence,
            reasoning=reasoning,
            supporting_events=self.history[-self.config.window_size:]
        )

    def _calculate_slope(self):
        # returns slope, r_squared
        if len(self.history) < self.config.window_size:
            return 0.0, 0.0
            
        data = self.history[-self.config.window_size:]
        n = len(data)
        if n < 2: return 0.0, 0.0
        
        # Simple Linear Regression: y = mx + c
        # X is just 0..n-1
        xs = range(n)
        ys = [e.value for e in data]
        
        mean_x = statistics.mean(xs)
        mean_y = statistics.mean(ys)
        
        numer = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
        denom = sum((x - mean_x) ** 2 for x in xs)
        
        if denom == 0: return 0.0, 0.0
        
        slope = numer / denom
        
        # R^2 calculation
        # SST = sum((y - mean_y)^2)
        # SSR = sum((pred_y - mean_y)^2)
        # but simpler: r = cov(x,y) / (std_x * std_y)
        return slope, 0.5 # Placeholder R2 for now if not strictly needed

    def get_conclusion(self) -> Sentiment:
        slope, _ = self._calculate_slope()
        
        # Normalize slope? Absolute value depends on data scale (e.g. 0.01 for traffic vs 100 for stocks)
        # We should use relative slope (slope / mean_value)
        
        if len(self.history) == 0: return Sentiment.STABLE
        last_val = self.history[-1].value
        if last_val == 0: last_val = 1e-9
        
        # Relative slope: % change per tick
        # rel_slope = slope / last_val 
        # But wait, self.config.slope_threshold is usually absolute?
        # To be generic, let's try to normalize or provide threshold via CLI relative to data.
        # Ideally, we calculate slope of standardized data?
        # For this refactor, let's use a simple heuristic:
        # If absolute slope > threshold * standard_deviation of window?
        
        # Let's use simple non-normalized slope but allow config to tune it.
        # Better: Trend is determined by consistent direction.
        
        if slope > self.config.slope_threshold:
            return Sentiment.UPTREND
        elif slope < -self.config.slope_threshold:
            return Sentiment.DOWNTREND
            
        return Sentiment.STABLE

    def get_confidence(self) -> float:
        # Confidence increases with window size and correlation quality
        min_history = min(5, self.config.window_size // 2)
        if len(self.history) < min_history:
            return 0.4 + (len(self.history) / min_history) * 0.2
            
        slope, _ = self._calculate_slope()
        
        data = self.history[-self.config.window_size:]
        n = len(data)
        if n < 3: return 0.5
        
        xs = range(n)
        ys = [e.value for e in data]
        
        # Calculate R (correlation coefficient) for confidence
        try:
             mx = statistics.mean(xs)
             my = statistics.mean(ys)
             numer = sum((x-mx)*(y-my) for x,y in zip(xs, ys))
             denom = math.sqrt(sum((x-mx)**2 for x in xs)) * math.sqrt(sum((y-my)**2 for y in ys))
             if denom == 0: 
                 r = 0
             else: 
                 r = numer / denom
             
             # Base confidence from linearity (R^2)
             r_squared = r ** 2
             
             # Slope strength also contributes
             slope_magnitude = abs(slope)
             slope_factor = 1.0 - math.exp(-slope_magnitude * 10)  # Normalize to 0..1
             
             # Combined confidence: linearity + slope strength
             confidence = 0.5 * r_squared + 0.3 * slope_factor + 0.2
             return min(max(confidence, 0.3), 1.0)
        except:
             return 0.5


class LongTermView(TemporalView):
    """Analyzes structural drift (Mean Reversion) using Z-scores over long history."""

    def __init__(self, name="LongTerm", config: ViewConfig = None):
         if config is None:
            config = ViewConfig(window_size=100, z_threshold=2.0, weight=1.5)
         super().__init__(name, config)

    def analyze(self) -> ViewConclusion:
        sentiment = self.get_conclusion()
        confidence = self.get_confidence()
        reasoning = f"Structure: {sentiment.value}. Conf: {confidence:.2f}."
        
        return ViewConclusion(
            view_name=self.name,
            time_scale="Long",
            sentiment=sentiment,
            confidence=confidence,
            reasoning=reasoning,
            supporting_events=[self.history[0], self.history[-1]] if self.history else []
        )

    def get_conclusion(self) -> Sentiment:
        if len(self.history) < max(20, self.config.window_size // 5):
            return Sentiment.STABLE

        values = [e.value for e in self.history]
        mean = statistics.mean(values)
        stdev = statistics.stdev(values) if len(values) > 1 else 1.0
        current = values[-1]
        
        if stdev == 0: stdev = 1e-9
        
        z_score = (current - mean) / stdev
        
        # Long term overextension
        # Long term overextension
        if z_score > self.config.z_threshold:
            return Sentiment.OVEREXTENDED_HIGH
        elif z_score < -self.config.z_threshold:
            return Sentiment.OVEREXTENDED_LOW
            
        return Sentiment.STABLE

    def get_confidence(self) -> float:
        # Confidence grows with dataset size and stability of the distribution
        if len(self.history) < 10: 
            return 0.3 + (len(self.history) / 10) * 0.2
        
        # Use coefficient of variation to assess distribution stability
        values = [e.value for e in self.history]
        mean_val = statistics.mean(values)
        stdev_val = statistics.stdev(values) if len(values) > 1 else 0
        
        if mean_val == 0 or stdev_val == 0:
            count_factor = min(len(self.history) / (self.config.window_size * 0.5), 1.0)
            return 0.5 + 0.35 * count_factor
        
        # CV measures stability: lower CV = more stable = higher confidence
        cv = stdev_val / abs(mean_val)
        stability_factor = 1.0 / (1.0 + cv)  # 0..1, higher is more stable
        
        count_factor = min(len(self.history) / (self.config.window_size * 0.5), 1.0)
        confidence = 0.4 * count_factor + 0.4 * stability_factor + 0.2
        return min(max(confidence, 0.3), 0.95)
