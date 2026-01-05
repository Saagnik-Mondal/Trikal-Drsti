# Critical Fixes Applied - Jan 4, 2026

## Problem: Decision Column Was Lying

**Before**: Single "DECISION: STABLE" column during CRASH emergency
**Issue**: Word "STABLE" had lost all meaning - actively dangerous during crisis

## Solution: Separation of Concerns

Split decision into **three orthogonal dimensions**:

### 1. System Posture (Conflict State)
- `STABLE`: No conflicts, views agree
- `CONTESTED`: 1-2 conflicts, manageable disagreement  
- `FRAGILE`: 3-5 conflicts, sensitive to changes
- `PRECARIOUS`: 5+ conflicts OR low structural legitimacy
- `CRITICAL`: Emergency override active

### 2. Structural Assessment (Long-term View)
- What does the Long-term view think about underlying structure?
- `STABLE`, `OVEREXTENDED_HIGH`, `OVEREXTENDED_LOW`, etc.
- Independent of whether Long-term wins the ruling

### 3. Action Recommendation
- `HOLD`: Stay course (STABLE sentiment)
- `MONITOR`: Watch closely (UPTREND/DOWNTREND)
- `CONTAIN`: At limits (OVEREXTENDED, VOLATILE)
- `ESCALATE`: Opportunity (SPIKE)
- `EXIT`: Danger (CRASH, emergency override)

## Example Output

```
CRITICAL state during crash:
  POSTURE:     CRITICAL
  STRUCTURE:   STABLE        (Long thinks it's fine)
  ACTION:      EXIT          (But ruling says get out)
  
  Short: CRASH   (85% confidence)
  Mid:   STABLE  (irrelevant during crisis)
  Long:  STABLE  (too slow to prevent catastrophe)
```

## Why This Matters

**Before**: "DECISION: STABLE" - User thinks everything is fine
**After**: "POSTURE: CRITICAL | STRUCTURE: STABLE | ACTION: EXIT" - User sees the tension

The system can now say:
- "I'm in CRITICAL emergency mode"
- "Structure thinks it's STABLE" 
- "But you should EXIT anyway"

**This is honest**. The word "STABLE" now only describes Long-term's structural assessment, not the system's overall recommendation.

## Implementation

### Backend (server.py)
- Added `_get_action()` mapping function
- Timeline now includes: `system_state`, `structural_view`, `action`
- Separated concerns preserved through entire pipeline

### Frontend (App.jsx)
- Timeline has 8 columns now (not 6):
  - TIME, VALUE
  - SHORT, MID, LONG (view assessments)
  - POSTURE (system conflict state)
  - STRUCTURE (Long-term structural view)
  - ACTION (recommended action)

### Color Coding
- **POSTURE**: Red=CRITICAL, Orange=PRECARIOUS, Yellow=FRAGILE, Cyan=CONTESTED
- **ACTION**: Red=EXIT, Orange=ESCALATE, Yellow=CONTAIN, Cyan=MONITOR

## Additional Fixes in This Session

### 1. Cumulative Pressure Tracking
- No longer waits for single 80% threshold
- Detects: 3+ warnings at 70%+ = cumulative pressure override
- Pattern: "whisper that won't stop" is now visible

### 2. Structural Legitimacy Degradation
- Long-term can now **lose credibility** (not just be overridden)
- Tracks override count: Each override → legitimacy drops 10%
- At <50% legitimacy: Structure loses ruling power
- System explicitly logs: "Structural legitimacy collapsed (40%)"

### 3. Robustness Warnings
- Every ruling now includes robustness assessment
- Examples:
  - "Rational under model. Robustness: UNKNOWN (no time for validation)" - Emergency
  - "Rational under mean-reversion model. Robustness depends on structural stability assumption." - Structural ruling
  - "Rational under scoring model. Robustness: LOW (narrow margin)" - Close call
  
### 4. System State Taxonomy
- Replaced binary threat_qualifier with 5-state posture system
- States reflect **conflict severity** not just danger presence
- FRAGILE → PRECARIOUS progression shows degrading confidence

## Test Results

```bash
$ Analysis of DataSummary.csv (128 events)

Status: completed | Conflicts: 3

CRITICAL states found: 1
  POSTURE: CRITICAL
  STRUCTURE: STABLE  
  ACTION: EXIT
  
  Short: CRASH (85% confidence)
  Mid: STABLE (suppressed)
  Long: STABLE (suppressed)

System Confidence: 60.8% (conflict-scaled)
```

## What Changed vs Previous Version

| Before | After |
|--------|-------|
| "DECISION: STABLE" | "POSTURE: CRITICAL \| STRUCTURE: STABLE \| ACTION: EXIT" |
| Single 80% threshold | Cumulative pressure detection |
| Structure assumed correct | Structure can degrade/lose legitimacy |
| "This ruling is correct" | "Rational under model. Robustness: LOW" |
| THREAT_QUALIFIER (binary) | SYSTEM_STATE (5-level taxonomy) |

## Critical Insight

**The system is no longer lying by omission.**

When structure says STABLE but action is EXIT:
- You see the contradiction immediately
- You understand: "Long thinks structure is fine, but Short detects irreversible crash"
- You can make informed decision: "Trust structure or trust urgency?"

Previously: System hid this tension behind "STABLE"
Now: System exposes the tension explicitly

---

**Status**: All four problems from user's critique have been addressed.
**Next**: Dynamic weight adjustment based on volatility regime (suggested future work)
