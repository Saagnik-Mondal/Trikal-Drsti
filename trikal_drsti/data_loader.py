import json
import os
from datetime import datetime, timedelta
from typing import Generator, List, Any
from .core import Event

class TaxiDataLoader:
    """Loads time-series data from the taxi_30min JSON format."""
    
    def __init__(self, file_path: str):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Dataset file not found: {file_path}")
        self.file_path = file_path

    def stream(self) -> Generator[Event, None, None]:
        """Reads the file and yields Events one by one."""
        # The file format seems to be line-delimited JSON or a list of JSON objects.
        # Based on the user's view, it looks like line-delimited JSON objects.
        # Format: {"start": "2015-01-01 00:00:00", "target": [v1, v2, ...], ...}
        
        with open(self.file_path, 'r') as f:
            for line_idx, line in enumerate(f):
                if not line.strip():
                    continue
                
                try:
                    entry = json.loads(line)
                    start_str = entry.get("start")
                    target = entry.get("target", [])
                    lat = entry.get("lat")
                    lng = entry.get("lng")
                    
                    if not start_str or not target:
                        continue

                    # Parse start time
                    start_time = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
                    
                    # Each value in 'target' is a time step (assuming 30min intervals based on dataset name 'taxi_30min')
                    # We will stream all points from this single line as a sequence
                    for i, value in enumerate(target):
                        # Calculate timestamp for this specific event
                        timestamp = start_time + timedelta(minutes=30 * i)
                        
                        yield Event(
                            timestamp=timestamp,
                            value=float(value),
                            description=f"Taxi demand at ({lat}, {lng})"
                        )
                        
                except json.JSONDecodeError:
                    print(f"Error decoding line {line_idx}")
                    continue
