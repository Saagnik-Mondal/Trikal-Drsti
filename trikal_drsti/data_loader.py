import json
import os
import re
from datetime import datetime, timedelta
from typing import Generator, List, Any, Tuple, Optional
from .core import Event

class UniversalLoader:
    """
    Universal Time-Series Loader - Accepts ANY format, ANY structure, ANY naming.
    Intelligently detects and extracts time-series data from:
    - CSV files (any delimiter, any column names)
    - JSON files (flat, nested, arrays, objects)
    - NDJSON files
    - Mixed formats
    """
    def __init__(self, file_path: str, dataset_name: str = "generic"):
        self.file_path = file_path
        self.dataset_name = dataset_name
        self.data_buffer = []
        self._load_data()

    def _load_data(self):
        print(f"[{self.dataset_name}] Loading data from {self.file_path}...")
        
        try:
            ext = os.path.splitext(self.file_path)[1].lower()
            
            if ext == '.csv':
                self._load_csv()
            else:
                # Try JSON first, fall back to other formats
                self._load_json()
            
            if not self.data_buffer:
                print(f"[{self.dataset_name}] WARNING: No data extracted. File may be empty or in unsupported format.")
            else:
                print(f"[{self.dataset_name}] Successfully loaded {len(self.data_buffer)} events.")
                
        except Exception as e:
            print(f"[{self.dataset_name}] Error loading data: {e}")
            # Try to extract ANY numeric data as a fallback
            try:
                self._extract_raw_numbers()
                if self.data_buffer:
                    print(f"[{self.dataset_name}] Fallback: Extracted {len(self.data_buffer)} numeric values")
                else:
                    raise e
            except:
                raise e

    def _extract_raw_numbers(self):
        """Last resort: extract any numeric sequences from file"""
        with open(self.file_path, 'r') as f:
            content = f.read()
        
        # Extract all floating point numbers
        numbers = re.findall(r'-?\d+\.?\d*', content)
        if len(numbers) < 2:
            return
        
        start_time = datetime(2000, 1, 1)
        for i, num_str in enumerate(numbers):
            try:
                val = float(num_str)
                self.data_buffer.append(Event(
                    timestamp=start_time + timedelta(hours=i),
                    value=val,
                    description="Fallback numeric extraction"
                ))
            except:
                pass

    def _load_csv(self):
        """Load CSV with intelligent column detection"""
        import csv
        
        with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
            # Auto-detect delimiter
            try:
                sample = f.read(4096)
                dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
                f.seek(0)
            except:
                f.seek(0)
                dialect = 'excel'
            
            reader = csv.reader(f, dialect=dialect)
            header = next(reader, None)
            
            if not header:
                raise ValueError("CSV file is empty")
            
            # Intelligent column detection
            time_idx, val_idx = self._detect_csv_columns(header)
            
            print(f"[{self.dataset_name}] Detected time column: {header[time_idx]}, value column: {header[val_idx]}")
            
            # Read all rows
            for row in reader:
                if len(row) <= max(time_idx, val_idx):
                    continue
                
                try:
                    t_str = str(row[time_idx]).strip()
                    v_str = str(row[val_idx]).strip()
                    
                    if not t_str or not v_str:
                        continue
                    
                    ts = self._parse_timestamp(t_str)
                    val = float(v_str)
                    
                    self.data_buffer.append(Event(timestamp=ts, value=val, description="CSV Source"))
                except (ValueError, TypeError):
                    continue

    def _detect_csv_columns(self, header: List[str]) -> Tuple[int, int]:
        """Intelligently detect timestamp and value columns"""
        time_patterns = [
            r'time', r'date', r'ts', r'timestamp', r'datetime', 
            r'created', r'updated', r'epoch', r'day', r'month', r'year'
        ]
        val_patterns = [
            r'value', r'val', r'target', r'price', r'amount', r'count',
            r'metric', r'measurement', r'data', r'reading', r'rate'
        ]
        
        time_idx = -1
        val_idx = -1
        
        # Score each column
        for i, col in enumerate(header):
            col_lower = col.lower().strip()
            
            # Time column detection
            if time_idx == -1:
                for pattern in time_patterns:
                    if re.search(pattern, col_lower):
                        time_idx = i
                        break
            
            # Value column detection
            if val_idx == -1:
                for pattern in val_patterns:
                    if re.search(pattern, col_lower):
                        val_idx = i
                        break
        
        # Fallback: first numeric column is likely value, before that is time
        if time_idx == -1 or val_idx == -1:
            for i, col in enumerate(header):
                col_lower = col.lower().strip()
                # Simple heuristics
                if time_idx == -1 and (len(col_lower) > 3 or col_lower in ['index', 'id']):
                    time_idx = i
                if val_idx == -1 and i > time_idx:
                    val_idx = i
        
        # Ultimate fallback
        if time_idx == -1:
            time_idx = 0
        if val_idx == -1:
            val_idx = min(1, len(header) - 1)
        
        return time_idx, val_idx

    def _parse_timestamp(self, t_str: str) -> datetime:
        """Parse timestamp in any format"""
        # Handle Unix timestamps
        try:
            ts_float = float(t_str)
            if ts_float > 100000000:  # Likely Unix timestamp
                return datetime.fromtimestamp(ts_float)
        except:
            pass
        
        # Try common formats
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d",
            "%d-%m-%Y %H:%M:%S",
            "%d-%m-%Y",
            "%B %d, %Y",
            "%b %d, %Y",
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(t_str, fmt)
            except:
                pass
        
        # Try ISO format variations
        try:
            # Handle ISO 8601 with timezone
            t_str_clean = t_str.replace('Z', '+00:00')
            return datetime.fromisoformat(t_str_clean.split('+')[0].split('-')[0:3])
        except:
            pass
        
        # Fallback: increment from epoch
        return datetime(2000, 1, 1)

    def _load_json(self):
        """Load JSON with intelligent data extraction"""
        raw_items = []
        
        with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        try:
            data = json.loads(content)
            raw_items = self._normalize_json_data(data)
        except json.JSONDecodeError:
            # Try NDJSON format
            raw_items = self._load_ndjson(content)
        
        if not raw_items:
            print(f"[{self.dataset_name}] No usable data found in JSON file")
            return
        for item in raw_items:
            self._extract_timeseries_from_item(item)

    def _normalize_json_data(self, data: Any) -> List[Any]:
        """Convert any JSON structure to list of items"""
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            # Check for common data formats
            if "data" in data:
                return self._normalize_json_data(data["data"])
            elif "items" in data:
                return self._normalize_json_data(data["items"])
            elif "records" in data:
                return self._normalize_json_data(data["records"])
            elif "values" in data:
                return self._normalize_json_data(data["values"])
            else:
                # Single object, check if it has time-series data
                return [data]
        return []

    def _load_ndjson(self, content: str) -> List[Any]:
        """Load newline-delimited JSON"""
        items = []
        for line in content.split('\n'):
            if line.strip():
                try:
                    items.append(json.loads(line))
                except:
                    pass
        return items

    def _extract_timeseries_from_item(self, item: Any):
        """Extract time-series data from any item structure"""
        if not isinstance(item, dict):
            return
        
        # Direct time-series format: {start, target}
        if "target" in item and isinstance(item["target"], list):
            self._process_start_target(item)
            return
        
        # Look for any array that could be values
        arrays = {k: v for k, v in item.items() if isinstance(v, list) and len(v) > 0}
        
        if not arrays:
            return
        
        # Try to identify the main data array
        candidates = []
        for key, arr in arrays.items():
            # Score based on key name and content
            score = 0
            key_lower = key.lower()
            
            if any(x in key_lower for x in ['target', 'value', 'data', 'metric', 'series']):
                score += 10
            
            # Check if array contains mostly numbers
            numeric_count = sum(1 for x in arr if isinstance(x, (int, float)))
            if numeric_count > len(arr) * 0.8:
                score += numeric_count
            
            candidates.append((score, key, arr))
        
        if not candidates:
            return
        
        # Use highest scoring array
        candidates.sort(reverse=True)
        best_key = candidates[0][1]
        values = candidates[0][2]
        
        # Extract numeric values
        start_time = item.get("start", datetime(2000, 1, 1))
        if isinstance(start_time, str):
            start_time = self._parse_timestamp(start_time)
        
        # Detect interval
        interval = timedelta(hours=1)
        if "30min" in self.file_path or "taxi" in self.dataset_name.lower():
            interval = timedelta(minutes=30)
        
        current_time = start_time
        for val in values:
            try:
                if isinstance(val, (list, dict)):
                    # Nested structure, try to extract number
                    if isinstance(val, list) and len(val) > 0:
                        val = val[0]
                    else:
                        continue
                
                numeric_val = float(val)
                self.data_buffer.append(Event(
                    timestamp=current_time,
                    value=numeric_val,
                    description=f"JSON Source: {best_key}"
                ))
            except (ValueError, TypeError):
                pass
            
            current_time += interval

    def _process_start_target(self, item: dict):
        """Process standard {start, target} format"""
        start_str = item.get("start", "2000-01-01 00:00:00")
        target_values = item.get("target", [])
        
        if isinstance(target_values, dict):
            return
        
        try:
            start_time = self._parse_timestamp(str(start_str))
        except:
            start_time = datetime(2000, 1, 1)
        
        # Detect interval
        interval = timedelta(hours=1)
        if "30min" in self.file_path or "taxi" in self.dataset_name.lower():
            interval = timedelta(minutes=30)
        
        current_time = start_time
        for val in target_values:
            try:
                if isinstance(val, list):
                    val = val[0]
                
                numeric_val = float(val)
                self.data_buffer.append(Event(
                    timestamp=current_time,
                    value=numeric_val,
                    description="Standard target format"
                ))
            except (ValueError, TypeError):
                pass
            
            current_time += interval

    def stream(self) -> Generator[Event, None, None]:
        """Stream events from buffer"""
        for event in self.data_buffer:
            yield event
