from dataclasses import dataclass
from datetime import datetime
from typing import Any, List, Optional
from abc import ABC, abstractmethod
from enum import Enum

class Sentiment(Enum):
    """
    Mathematical sentiment definitions:
    - UPTREND: Positive slope > threshold
    - DOWNTREND: Negative slope < -threshold
    - STABLE: Slope within [-threshold, threshold]
    - SPIKE: Value > mean + (Z * std_dev)
    - CRASH: Value < mean - (Z * std_dev)
    - VOLATILE: Std_dev > volatility_threshold
    """
    UPTREND = "UPTREND"
    DOWNTREND = "DOWNTREND"
    STABLE = "STABLE"
    SPIKE = "SPIKE"
    CRASH = "CRASH"
    VOLATILE = "VOLATILE"
    OVEREXTENDED_HIGH = "OVEREXTENDED_HIGH" # Z-score >> Threshold (Expect mean reversion DOWN)
    OVEREXTENDED_LOW = "OVEREXTENDED_LOW"   # Z-score << -Threshold (Expect mean reversion UP)

@dataclass
class ViewConfig:
    """Configuration for a Temporal View."""
    window_size: int
    z_threshold: float = 2.5
    slope_threshold: float = 0.05
    weight: float = 1.0

@dataclass
class Event:
    """A single point in time in the data stream."""
    timestamp: datetime
    value: float
    description: Optional[str] = None

@dataclass
class ViewConclusion:
    """The result of a temporal view's analysis."""
    view_name: str
    time_scale: str
    sentiment: Sentiment
    confidence: float # 0.0 to 1.0
    reasoning: str
    supporting_events: List[Event]

class TemporalView(ABC):
    """Abstract base class for all time-scale views."""
    
    def __init__(self, name: str, config: ViewConfig):
        self.name = name
        self.config = config
        self.history: List[Event] = []

    def add_event(self, event: Event):
        self.history.append(event)
        # Keep history bounded with a buffer for calc (e.g. 2x window)
        # We need enough history for rolling stats
        limit = max(self.config.window_size * 2, 50) 
        if len(self.history) > limit:
            self.history.pop(0)

    @abstractmethod
    def analyze(self) -> ViewConclusion:
        """Analyze the current history and return a conclusion."""
        pass
        
    @abstractmethod
    def get_conclusion(self) -> Sentiment:
        """Return the core sentiment (enum) of the analysis."""
        pass

    @abstractmethod
    def get_confidence(self) -> float:
        """Return a normalized confidence score (0.0 - 1.0)."""
        pass
