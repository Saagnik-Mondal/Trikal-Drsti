from dataclasses import dataclass
from datetime import datetime
from typing import Any, List, Optional
from abc import ABC, abstractmethod

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
    sentiment: str  # e.g., "RISING", "FALLING", "STABLE", "VOLATILE"
    confidence: float
    reasoning: str
    supporting_events: List[Event]

class TemporalView(ABC):
    """Abstract base class for all time-scale views."""
    
    def __init__(self, name: str, window_size: int):
        self.name = name
        self.window_size = window_size
        self.history: List[Event] = []

    def add_event(self, event: Event):
        self.history.append(event)
        # Keep history bounded, though views might need more than window_size 
        # for calculation (e.g. diffs), so we keep a bit of buffer.
        if len(self.history) > self.window_size * 2:
            self.history.pop(0)

    @abstractmethod
    def analyze(self) -> ViewConclusion:
        """Analyze the current history and return a conclusion."""
        pass
