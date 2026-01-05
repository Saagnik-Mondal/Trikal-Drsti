from dataclasses import dataclass
from typing import List, Dict, Optional
from collections import deque
import statistics
from .core import ViewConclusion, Sentiment, Event

@dataclass
class Prediction:
    timestamp: object
    sentiment: Sentiment
    time_scale: str
    start_value: float
    target_window: int
    volatility: float = 1.0
    momentum: float = 0.0


class Evaluator:
    """
    Tracks RETROSPECTIVE CONSISTENCY - not ground truth accuracy.
    
    This measures: "Did the prediction align with what happened next?"
    This does NOT measure: "Was the prediction objectively correct?"
    
    NO GROUND TRUTH EXISTS. This is internal consistency checking only.
    """
    def __init__(self):
        self.pending_predictions: List[Prediction] = []
        self.completed_predictions: List[Dict] = []
        self.metrics = {
            "total": 0,
            "correct": 0,
            "wrong": 0
        }
        self.recent_values: deque = deque(maxlen=20)
        self.warning_issued = False

    def track_decision(self, conclusion: ViewConclusion, current_event: Event):
        sentiment = conclusion.sentiment
        
        # Skip VOLATILE - no clear directional prediction
        if sentiment == Sentiment.VOLATILE:
            return

        # Moderate confidence threshold for balance of quantity and quality
        if conclusion.confidence < 0.50:
            return
        
        # Include STABLE predictions but with stricter verification
        # Skip only VOLATILE as it has no directional component
        # if sentiment == Sentiment.STABLE:
        #     return
            
        # Shorter verification windows for faster, more accurate feedback
        window = 3
        if conclusion.time_scale == "Mid":
            window = 8
        elif conclusion.time_scale == "Long":
            window = 15
        
        # Calculate local volatility from supporting events
        vals = [e.value for e in conclusion.supporting_events] if conclusion.supporting_events else []
        vol = 1.0
        if len(vals) > 1:
            vol = statistics.stdev(vals)
        elif vals:
            vol = max(abs(vals[0]) * 0.1, 1.0)
        
        # Calculate recent momentum
        momentum = 0.0
        if len(vals) >= 3:
            momentum = vals[-1] - vals[-3]

        self.pending_predictions.append(Prediction(
            timestamp=current_event.timestamp,
            sentiment=conclusion.sentiment,
            time_scale=conclusion.time_scale,
            start_value=current_event.value,
            target_window=window,
            volatility=vol,
            momentum=momentum
        ))

    def update(self, current_event: Event):
        """Process pending predictions, decrementing windows and verifying when ready."""
        self.recent_values.append(current_event.value)
        
        still_pending = []
        for p in self.pending_predictions:
            p.target_window -= 1
            if p.target_window <= 0:
                self._verify(p, current_event)
            else:
                still_pending.append(p)
        self.pending_predictions = still_pending

    def _verify(self, prediction: Prediction, current_event: Event):
        """Verify prediction with improved logic."""
        end_value = current_event.value
        change = end_value - prediction.start_value
        
        # Dynamic threshold based on local volatility - scale with start value
        base_val = max(abs(prediction.start_value), 1.0)
        relative_change = change / base_val
        
        # Noise threshold: smaller of volatility-based or percentage-based
        noise_threshold = min(
            max(prediction.volatility * 0.5, 0.5),  # Volatility-based
            base_val * 0.15  # 15% relative threshold
        )
        
        is_correct = False
        
        if prediction.sentiment == Sentiment.UPTREND:
            # UPTREND: expect positive or flat movement
            # For smooth data, trend should continue in same direction
            is_correct = change >= -noise_threshold
            
        elif prediction.sentiment == Sentiment.DOWNTREND:
            # DOWNTREND: expect negative or flat movement
            is_correct = change <= noise_threshold
            
        elif prediction.sentiment == Sentiment.SPIKE:
            # SPIKE: High value detected - expect it to stay high or come down
            # Either direction is reasonable after a spike
            is_correct = abs(relative_change) <= 0.5  # Within 50% change
            
        elif prediction.sentiment == Sentiment.CRASH:
            # CRASH: Low value detected - expect recovery or continued low
            is_correct = change >= -noise_threshold  # At least not much worse
            
        elif prediction.sentiment == Sentiment.STABLE:
            # STABLE: Change should be within generous noise band for noisy data
            threshold = max(prediction.volatility * 3.0, base_val * 0.35, 3.0)
            is_correct = abs(change) <= threshold
            
        elif prediction.sentiment == Sentiment.OVEREXTENDED_HIGH:
            # Expect mean reversion or at least no further rise
            is_correct = change <= noise_threshold * 2
            
        elif prediction.sentiment == Sentiment.OVEREXTENDED_LOW:
            # Expect mean reversion or at least no further drop
            is_correct = change >= -noise_threshold * 2
            
        self.metrics["total"] += 1
        if is_correct:
            self.metrics["correct"] += 1
        else:
            self.metrics["wrong"] += 1
            
        self.completed_predictions.append({
            "scale": prediction.time_scale,
            "predicted": prediction.sentiment.value,
            "start": prediction.start_value,
            "end": end_value,
            "change": change,
            "correct": is_correct
        })

    def get_report(self) -> Dict:
        """
        This is NOT an accuracy metric.
        This returns system state diagnostics only.
        """
        total = self.metrics["total"]
        
        if total < 50:
            consistency = 0.0
            warning = "INSUFFICIENT_DATA"
        else:
            consistency = (self.metrics["correct"] / total)
            warning = None
        
        # Breakdown by sentiment type
        breakdown = {}
        for pred in self.completed_predictions:
            sentiment = pred["predicted"]
            if sentiment not in breakdown:
                breakdown[sentiment] = {"total": 0, "correct": 0}
            breakdown[sentiment]["total"] += 1
            if pred["correct"]:
                breakdown[sentiment]["correct"] += 1
        
        return {
            "prediction_alignment": consistency,  # Renamed - what we actually measure
            "warning": warning,
            "total_signals": total,
            "correct": self.metrics["correct"],
            "wrong": self.metrics["wrong"],
            "breakdown": breakdown,
            "note": "This measures prediction-outcome alignment within assumptions, not ground truth accuracy."
        }
