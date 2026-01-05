from datetime import datetime, timedelta
import random
from trikal_drsti.core import Event, ViewConfig, Sentiment, ViewConclusion
from trikal_drsti.views import ShortTermView, MidTermView, LongTermView
from trikal_drsti.resolution import ConflictDetector, ResolutionEngine, ViewWeightConfig

def generate_mock_stream(length=200, pattern="stable"):
    base_time = datetime(2025, 1, 1)
    events = []
    val = 100.0
    for i in range(length):
        if pattern == "stable":
            val += random.uniform(-0.5, 0.5)
        elif pattern == "uptrend":
            val += random.uniform(0, 1.0)
        elif pattern == "spike":
            if i > length - 10: val += 10.0 # Huge spike at end
            else: val += random.uniform(-0.5, 0.5)
        
        events.append(Event(base_time + timedelta(hours=i), val))
    return events

def test_view_invariants():
    print("\n[TEST] View Invariants (Confidence 0-1, Valid Sentiment)")
    
    # Setup
    views = [
        ShortTermView(config=ViewConfig(window_size=10, z_threshold=2.0)),
        MidTermView(config=ViewConfig(window_size=20)),
        LongTermView(config=ViewConfig(window_size=50))
    ]
    
    stream = generate_mock_stream(length=100, pattern="uptrend")
    
    for i, event in enumerate(stream):
        for view in views:
            view.add_event(event)
            conclusion = view.analyze()
            
            # Assertions
            assert 0.0 <= conclusion.confidence <= 1.0, f"Confidence out of bounds: {conclusion.confidence} for {view.name}"
            assert isinstance(conclusion.sentiment, Sentiment), f"Invalid sentiment type: {type(conclusion.sentiment)}"
            assert conclusion.time_scale in ["Short", "Mid", "Long"], "Invalid time scale"
            
    print("✅ All view invariants passed.")

def test_resolution_logic():
    print("\n[TEST] Resolution Logic (Weighted consensus)")
    
    # Create conflicting conclusions manually
    # Case A: Pure Score Competition (No overrides)
    # Short: 0.9 * 0.5 = 0.45
    # Mid:   0.6 * 1.0 = 0.60
    # Long:  0.8 * 1.5 = 1.20 -> Winner
    
    c1 = ViewConclusion("Short", "Short", Sentiment.DOWNTREND, 0.9, "Sad", []) 
    c2 = ViewConclusion("Mid", "Mid", Sentiment.UPTREND, 0.6, "Still going up", [])
    c3 = ViewConclusion("Long", "Long", Sentiment.STABLE, 0.8, "Chill", [])
    
    resolver = ResolutionEngine(ViewWeightConfig(weights={"Short": 0.5, "Mid": 1.0, "Long": 1.5}))
    
    decision = resolver.resolve([c1, c2, c3], [])
    print(f"Decision A (Score): {decision.primary_conclusion.time_scale}")
    
    assert decision.primary_conclusion.time_scale == "Long", "Weighted logic failed to pick highest score (Long)"
    print("✅ Weighted logic passed.")

    # Case B: Safety Override
    # Short CRASH with High Confidence -> Should override Long
    c1_critical = ViewConclusion("Short", "Short", Sentiment.CRASH, 0.95, "Panic", [])
    
    decision_override = resolver.resolve([c1_critical, c2, c3], [])
    print(f"Decision B (Override): {decision_override.primary_conclusion.time_scale}")
    assert decision_override.primary_conclusion.time_scale == "Short", "Safety override failed to trigger"
    print("✅ Safety override passed.")

    # Case C: Low Confidence Crash (Should NOT override, should use Weighted Score)
    # Short: CRASH (0.4) * 0.5 = 0.2
    # Mid: MID (0.6) * 1.0 = 0.6
    # Long: LONG (0.8) * 1.5 = 1.2
    # Winner: Long
    
    c1_weak = ViewConclusion("Short", "Short", Sentiment.CRASH, 0.4, "Maybe panic?", [])
    
    decision_weak = resolver.resolve([c1_weak, c2, c3], [])
    print(f"Decision C (Weak Crash): {decision_weak.primary_conclusion.time_scale}")
    
    # It should NOT be Short. It should be Long (highest score).
    assert decision_weak.primary_conclusion.time_scale == "Long", "Low confidence crash incorrectly triggered override"
    print("✅ Low confidence fallback passed.")

if __name__ == "__main__":
    try:
        test_view_invariants()
        test_resolution_logic()
        print("\n🎉 ALL CORE TESTS PASSED")
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        exit(1)
