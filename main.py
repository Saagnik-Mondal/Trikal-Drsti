import time
import sys
import argparse
from trikal_drsti.data_loader import UniversalLoader
from trikal_drsti.views import ShortTermView, MidTermView, LongTermView
from trikal_drsti.resolution import ConflictDetector, ResolutionEngine, ViewWeightConfig
from datetime import datetime
from trikal_drsti.core import ViewConfig, Sentiment, ViewConclusion

# Sample Data Paths (You would likely load these from config)
DATASETS = {
    "taxi": "../taxi_30min/train/train.json",
    "traffic": "../traffic_nips/train/data.json",
    "electricity": "../electricity_nips/train/data.json"
}

def main():
    parser = argparse.ArgumentParser(description="Trikal-Drsti Temporal Reasoning Engine")
    parser.add_argument("--dataset", type=str, default="taxi", help="Dataset key (taxi, traffic) OR path to custom JSON file")
    parser.add_argument("--short-window", type=int, default=10, help="Window size for ShortTerm view")
    parser.add_argument("--mid-window", type=int, default=30, help="Window size for MidTerm view")
    parser.add_argument("--long-window", type=int, default=100, help="Window size for LongTerm view")
    parser.add_argument("--z-threshold", type=float, default=2.5, help="Z-score threshold for anomalies")
    parser.add_argument("--slope-threshold", type=float, default=0.001, help="Slope threshold for trend detection")
    parser.add_argument("--plot", action="store_true", help="Generate Sci-Fi style visualization at end")
    args = parser.parse_args()

    # Determine path: check if it's a key in DATASETS, otherwise treat as file path
    if args.dataset in DATASETS:
        dataset_name = args.dataset
        dataset_path = DATASETS[args.dataset]
    else:
        dataset_name = "custom"
        dataset_path = args.dataset
        print(f"[Info] Using custom dataset file: {dataset_path}")

    print(f"--- Trikal-Drsti: Temporal Reasoning Engine ---")
    print(f"Dataset: {dataset_name} | Logic: Weighted Consensus")
    print(f"Path: {dataset_path}")
    
    loader = UniversalLoader(dataset_path, dataset_name)
    
    # buffers for visualization
    history_data = [] # (timestamp, value)
    history_conclusions = [] # dicts
    
    # 2. Initialize Views with Configuration
    views = [
        ShortTermView(config=ViewConfig(window_size=args.short_window, z_threshold=args.z_threshold, slope_threshold=args.slope_threshold, weight=0.5)),
        MidTermView(config=ViewConfig(window_size=args.mid_window, slope_threshold=args.slope_threshold, weight=1.0)),
        LongTermView(config=ViewConfig(window_size=args.long_window, z_threshold=args.z_threshold + 0.5, slope_threshold=args.slope_threshold, weight=1.5))
    ]
    
    # 3. Initialize Reasoning
    detector = ConflictDetector()
    resolver = ResolutionEngine(ViewWeightConfig(weights={"Short": 0.5, "Mid": 1.0, "Long": 1.5}))
    
    from trikal_drsti.evaluation import Evaluator
    evaluator = Evaluator()
    
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
                conclusion = view.analyze()
                conclusions.append(conclusion)
                
                # buffer for plot
                if args.plot:
                    history_conclusions.append({
                        'timestamp': event.timestamp,
                        'layer': conclusion.time_scale,
                        'sentiment': conclusion.sentiment.value,
                        'confidence': conclusion.confidence
                    })
                
            # B. Detect Conflicts
            conflicts = detector.detect(conclusions)
            
            # C. Resolve Decision
            decision = resolver.resolve(conclusions, conflicts)
            
            # Update Evaluator (Forward Testing)
            # Track the PRIMARY decision
            evaluator.track_decision(decision.primary_conclusion, event)
            evaluator.update(event)
            
            # buffer data
            if args.plot:
                history_data.append((event.timestamp, event.value))
            
            # D. Traceable Output
            
            # ANSI Colors
            RED = '\033[91m'
            GREEN = '\033[92m'
            YELLOW = '\033[93m'
            BLUE = '\033[94m'
            MAGENTA = '\033[95m'
            CYAN = '\033[96m'
            RESET = '\033[0m'
            
            timestamp_str = event.timestamp.strftime("%Y-%m-%d %H:%M")
            val_str = f"{event.value:.2f}"
            
            # Helper to get financial-style colors
            def get_color(s: Sentiment):
                if s in [Sentiment.UPTREND, Sentiment.SPIKE]: return GREEN
                if s in [Sentiment.DOWNTREND, Sentiment.CRASH]: return RED
                if s == Sentiment.VOLATILE: return YELLOW
                if s == Sentiment.OVEREXTENDED_HIGH: return MAGENTA
                if s == Sentiment.OVEREXTENDED_LOW: return CYAN
                return RESET

            # Status line
            status = f"[{timestamp_str}] Val: {val_str:<6} | "
            for c in conclusions:
                color = get_color(c.sentiment)
            
            # Only print every tick? Or filter? 
            # For "Sci-Fi" feel, we print every tick but keep it clean.
            # If conflicts or low confidence, we expand.
            
            if conflicts or decision.primary_conclusion.confidence < 0.6 or event_count % 10 == 0:
                print(status)
                
                if conflicts:
                    print(f"   {YELLOW}⚠ CONFLICT DETECTED:{RESET}")
                    for conf in conflicts:
                        print(f"     - {conf.description}")
                
                    dom_color = get_color(decision.primary_conclusion.sentiment)
                    print(f"   {BLUE}➤ RESOLUTION:{RESET} Trusting {dom_color}{decision.primary_conclusion.time_scale}{RESET} ({decision.primary_conclusion.sentiment.value})")
                    print(f"     Reason: {decision.explanation}")
                    print("-" * 80)
            
            if event_count > 500:
                print("\n[Simulation Limit Reached for Demo]")
                break
        
        # Final Report
        report = evaluator.get_report()
        print(f"\n{BLUE}--- Performance Report (Predictive Validation) ---{RESET}")
        print(f"Total Directional Signals Verified: {report['total_signals']}")
        print(f"Correct Predictions (Forward Trend): {report['correct']}")
        print(f"Accuracy: {report['accuracy']*100:.1f}%")
        
        # Print breakdown by sentiment type
        if 'breakdown' in report and report['breakdown']:
            print(f"\n{CYAN}Accuracy by Sentiment Type:{RESET}")
            for sentiment, stats in report['breakdown'].items():
                sent_acc = (stats['correct'] / stats['total'] * 100) if stats['total'] > 0 else 0
                print(f"  {sentiment}: {stats['correct']}/{stats['total']} ({sent_acc:.1f}%)")

        if args.plot:
            try:
                from visualize import visualize
                print("\nGenerating Visualization...")
                visualize(history_data, history_conclusions)
            except ImportError as e:
                print(f"\n[Warning] Visualization failed: {e}. Please ensure matplotlib is installed.")
            except Exception as e:
                print(f"\n[Error] Visualization failed: {e}")
                
    except FileNotFoundError:
        print("Error: Dataset file not found.")
    except KeyboardInterrupt:
        print("\nAnalysis manual stop.")
        
        # Report on interrupt too
        report = evaluator.get_report()
        print(f"\n--- Performance Report (Partial) ---")
        print(f"Accuracy: {report['accuracy']*100:.1f}% ({report['correct']}/{report['total_signals']})")

        if args.plot:
            try:
                from visualize import visualize
                print("\nGenerating Visualization...")
                visualize(history_data, history_conclusions)
            except ImportError:
                print(f"\n[Warning] Visualization failed: Matplotlib not installed.")
            except Exception as e:
                print(f"\n[Error] Visualization failed: {e}")

if __name__ == "__main__":
    main()
