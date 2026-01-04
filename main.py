import time
import sys
from trikal_drsti.data_loader import TaxiDataLoader
from trikal_drsti.views import ShortTermView, MidTermView, LongTermView
from trikal_drsti.resolution import ConflictDetector, ResolutionEngine

def main():
    # 1. Setup Data Source
    # Using the train.json from the user's workspace
    dataset_path = "../taxi_30min/train/train.json" 
    print(f"--- Trikal-Drsti: Temporal Reasoning Engine ---")
    print(f"Loading data from: {dataset_path}")
    
    loader = TaxiDataLoader(dataset_path)
    
    # 2. Initialize Views
    views = [
        ShortTermView(window_size=5),   # Very reactive
        MidTermView(window_size=24),    # ~12 hours (24 * 30mins)
        LongTermView(window_size=336)   # ~1 week (336 * 30mins)
    ]
    
    # 3. Initialize Reasoning
    detector = ConflictDetector()
    resolver = ResolutionEngine()
    
    # 4. Event Loop
    print("\nStarting Stream Analysis...\n")
    try:
        event_count = 0
        for event in loader.stream():
            event_count += 1
            
            # A. Update Views
            conclusions = []
            for view in views:
                view.add_event(event)
                conclusions.append(view.analyze())
                
            # B. Detect Conflicts
            conflicts = detector.detect(conclusions)
            
            # C. Resolve Decision
            decision = resolver.resolve(conclusions, conflicts)
            
            # D. Traceable Output (Print only significant updates or periodic logs)
            # We print every step for demonstration, but formatted concisely
            
            # Use ANSI colors for terminal output
            RED = '\033[91m'
            GREEN = '\033[92m'
            YELLOW = '\033[93m'
            BLUE = '\033[94m'
            RESET = '\033[0m'
            
            timestamp_str = event.timestamp.strftime("%Y-%m-%d %H:%M")
            val_str = f"{event.value:.2f}"
            
            # Status line
            status = f"[{timestamp_str}] Value: {val_str:<6} | "
            for c in conclusions:
                color = RESET
                if c.sentiment in ["RISING", "SPIKE", "OVEREXTENDED_HIGH"]: color = GREEN
                elif c.sentiment in ["FALLING", "CRASH", "OVEREXTENDED_LOW"]: color = RED
                elif c.sentiment == "VOLATILE": color = YELLOW
                
                status += f"{c.time_scale}: {color}{c.sentiment:<10}{RESET} "
            
            print(status)
            
            # Conflict / Resolution Block (Only if interesting stuff is happening)
            if conflicts or decision.primary_conclusion.confidence < 0.6:
                print(f"   {YELLOW}⚠ CONFLICT DETECTED:{RESET}")
                for conf in conflicts:
                    print(f"     - {conf.description}")
                
                dom_color = GREEN if decision.primary_conclusion.sentiment in ["RISING", "SPIKE"] else RED
                print(f"   {BLUE}➤ RESOLUTION:{RESET} Trusting {dom_color}{decision.primary_conclusion.time_scale} ({decision.primary_conclusion.sentiment}){RESET}")
                print(f"     Why: {decision.explanation}")
                print(f"     Trace: Based on {len(decision.primary_conclusion.supporting_events)} events from {decision.primary_conclusion.supporting_events[0].timestamp} to {decision.primary_conclusion.supporting_events[-1].timestamp}")
                print("-" * 80)
            
            # Artificial delay for demo feel (remove for production speed)
            # time.sleep(0.05) 
            
            if event_count > 500:
                print("\n[Simulation Limit Reached for Demo]")
                break
                
    except FileNotFoundError:
        print("Error: Dataset file not found. Please ensure 'taxi_30min/train/train.json' exists.")
    except KeyboardInterrupt:
        print("\nAnalysis manual stop.")

if __name__ == "__main__":
    main()
