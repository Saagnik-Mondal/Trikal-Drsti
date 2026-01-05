# Trikal-Drsti: Temporal Reasoning Engine

Trikal-Drsti ("Three-Time Vision") is a mathematically rigorous temporal reasoning system designed to analyze time-series data across multiple scales (Short, Mid, Long). It resolves conflicting signals using a weighted consensus mechanism with safety overrides.

## Features

- **Multi-Scale Analysis**: Simultaneously analyzes Short-term (Z-score), Mid-term (Linear Regression), and Long-term (Structural Deviation) trends.
- **Weighted Consensus**: Resolves conflicts by calculating `Score = Confidence * Weight`.
- **Safety Overrides**: Automatically prioritizes high-confidence crashes over long-term stability.
- **Traceable Reasoning**: Outputs "Sci-Fi" style logs with explicit mathematical justification for every decision.
- **Visualizations**: Generates dark-mode timeline plots for post-analysis review.

## Usage

### Basic Run
```bash
python main.py --dataset taxi
```

### Advanced Configuration
```bash
python main.py --dataset electricity \
  --short-window 10 \
  --mid-window 50 \
  --long-window 200 \
  --z-threshold 3.0 \
  --plot
```

### CLI Arguments
| Argument | Default | Description |
| :--- | :--- | :--- |
| `--dataset` | `taxi` | Dataset key (`taxi`, `traffic`, `electricity`) **OR** path to custom JSON file. |
| `--short-window` | `10` | Window size for ShortTerm view (Volatility/Noise). |
| `--mid-window` | `30` | Window size for MidTerm view (Trend). |
| `--long-window` | `100` | Window size for LongTerm view (Structure). |
| `--z-threshold` | `2.5` | Standard deviations required to trigger `SPIKE`/`CRASH`. |
| `--plot` | `False` | Enable Matplotlib visualization output (`trikal_drsti_vis.png`). |

## 📂 Custom Data
To analyze your own data, create a JSON file (e.g., `my_data.json`) with the following format:
```json
[
    {
        "start": "2025-01-01 00:00:00",
        "target": [10.0, 10.5, 11.0, 15.0, 10.0]
    }
]
```
Then run:
```bash
python main.py --dataset my_data.json --plot
```

## Core Logic

### 1. Sentiment Enums
The system classifies market/signal states into strictly defined Enums:
- **`UPTREND`**: Positive slope > threshold.
- ****`DOWNTREND`**: Negative slope < -threshold.
- **`STABLE`**: Slope/Volatility within normal bounds.
- **`SPIKE`**: Sudden upward deviation > Z-threshold.
- **`CRASH`**: Sudden downward deviation < -Z-threshold.
- **`VOLATILE`**: High variance without clear direction.
- **`OVEREXTENDED`**: Structural deviation from long-term mean (reversion risk).

### 2. View Architecture
| View | Method | Detects | Weight |
| :--- | :--- | :--- | :--- |
| **ShortTerm** | Z-Score (Rolling) | `SPIKE`, `CRASH`, `VOLATILE` | 0.5 |
| **MidTerm** | Linear Regression Slope | `UPTREND`, `DOWNTREND` | 1.0 |
| **LongTerm** | Global Z-Score | `OVEREXTENDED`, `STABLE` | 1.5 |

### 3. Resolution Logic
The **ResolutionEngine** determines the final output state:

1.  **Weighted Score**: `Score = Confidence * Weight`. The view with the highest score wins.
2.  **Safety Override**: If **ShortTerm** detects `CRASH` with confidence > 0.8, it overrides all other signals immediately to prioritize safety.
3.  **Conflict Detection**: Explicitly flags contradictions (e.g., Short-term Volatility vs. Long-term Stability).

## Visualization
When running with `--plot`, the system generates `trikal_drsti_vis.png`:
- **Top Panel**: The raw signal value.
- **Bottom Panel**: Confidence levels for Short, Mid, and Long term views over time.
