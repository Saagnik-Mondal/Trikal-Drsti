import math
import random
import time
from datetime import datetime, timedelta
from typing import Generator
from .core import Event

class StreamGenerator:
    """Generates a synthetic data stream with encoded multi-scale patterns."""
    
    def __init__(self, start_value: float = 100.0, speed: float = 0.1):
        self.current_value = start_value
        self.tick_count = 0
        self.speed = speed
        self._start_time = datetime.now()

    def generate(self) -> Generator[Event, None, None]:
        """Yields an infinite stream of Events."""
        while True:
            # 1. Long Term Component: Slow upward drift
            # Every 100 ticks, it goes up significantly, but barely noticeable per tick
            drift = self.tick_count * 0.005  

            # 2. Mid Term Component: Sine wave (Cycles every 50 ticks)
            # Amplitude 5.0
            mid_term_trend = 5.0 * math.sin(self.tick_count * 0.12) 

            # 3. Short Term Component: High frequency noise
            # Random uniform noise between -2.0 and 2.0
            noise = random.uniform(-2.0, 2.0)

            # Combine them
            # We want cases where Noise contradicts Trend or Trend contradicts Drift
            value = self.current_value + drift + mid_term_trend + noise

            # Create event
            evt = Event(
                timestamp=self._start_time + timedelta(seconds=self.tick_count),
                value=round(value, 2),
                description=f"Tick {self.tick_count}"
            )
            
            yield evt
            
            self.tick_count += 1
            time.sleep(self.speed)
