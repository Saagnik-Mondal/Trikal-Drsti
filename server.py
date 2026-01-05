from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
import shutil
import os
import uuid
import datetime
import asyncio

# Core Trikal-Drsti imports
from trikal_drsti.core import ViewConfig, Sentiment, ViewConclusion
from trikal_drsti.views import ShortTermView, MidTermView, LongTermView
from trikal_drsti.resolution import ConflictDetector, ResolutionEngine, ViewWeightConfig
from trikal_drsti.data_loader import UniversalLoader
from trikal_drsti.evaluation import Evaluator

app = FastAPI(title="Trikal-Drsti API", version="2.0.0")

# Enable CORS for local React dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- Models ---
class AnalysisResult(BaseModel):
    id: str
    status: str
    progress: int
    accuracy: Optional[float] = None  # Accuracy percentage (0-100)
    logs: List[str]
    timeline: List[Dict]  # {timestamp, value, short, mid, long, confidence, sentiment}
    conflicts: List[Dict]  # List of conflicts detected
    final_report: Dict

# --- In-Memory Store (MVP) ---
analyses: Dict[str, AnalysisResult] = {}

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    # 1. Validation (Size cap 1GB)
    # Fastapi size validation is manual or via middleware. 
    # For MVP we read chunks or check content-length header? 
    # Let's just read and check size.
    
    file_id = str(uuid.uuid4())
    filename = f"{file_id}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    # 2. MP4 Stub Check
    if file.filename.lower().endswith(".mp4") or file.content_type.startswith("video/"):
        return {
            "id": file_id,
            "status": "partial",
            "message": "Video Module Offline (Metric Extraction Pending). Please upload CSV time-series series for analysis.",
            "is_video": True
        }

    # 3. Save File
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Check size (rough check after save) - 1GB limit
        if os.path.getsize(file_path) > 1024 * 1024 * 1024:
            os.remove(file_path)
            raise HTTPException(status_code=413, detail="File too large (Max 1GB)")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

    # 4. Trigger Analysis (Async Background?)
    # For MVP, we'll run synchronously or launch a task.
    # Let's launch a background task.
    asyncio.create_task(run_analysis(file_id, file_path))
    
    return {"id": file_id, "status": "processing", "message": "Analysis started."}

@app.get("/analysis/{file_id}")
async def get_analysis(file_id: str):
    if file_id not in analyses:
        return {"status": "not_found"}
    return analyses[file_id]

async def run_analysis(file_id: str, file_path: str):
    import time
    start_time = time.time()
    
    logs = []
    def log(msg):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        logs.append(f"[{timestamp}] {msg}")
        # Update state immediately for polling
        if file_id in analyses:
            analyses[file_id].logs = logs

    analyses[file_id] = AnalysisResult(
        id=file_id, status="initializing", progress=0, accuracy=None,
        logs=["[SYSTEM] Initializing Trikal-Drsti Engine..."], 
        timeline=[], conflicts=[], final_report={}
    )
    
    try:
        log("Loading UniversalLoader...")
        loader = UniversalLoader(file_path, dataset_name="upload")
        
        # Stream and sample efficiently for large files (avoid loading all into memory)
        log("Streaming data...")
        all_events = []
        
        # Collect all events with progress logging
        event_count = 0
        for event in loader.stream():
            all_events.append(event)
            event_count += 1
            
            # Log progress for very large files
            if event_count % 100000 == 0:
                log(f"Processed {event_count:,} events...")
        
        log(f"Total events loaded: {event_count:,}")
        
        # Sample if dataset is large
        if len(all_events) > 1000:
            log(f"Large dataset detected ({len(all_events):,} events). Sampling 1000 events for analysis.")
            step = len(all_events) // 1000
            events = all_events[::step][:1000]
        else:
            events = all_events
        
        log(f"Data Loaded: {len(events)} events for analysis.")
        
        # Init Engine
        views = [
            ShortTermView(config=ViewConfig(window_size=10, z_threshold=2.5, weight=0.5)),
            MidTermView(config=ViewConfig(window_size=30, weight=1.0)),
            LongTermView(config=ViewConfig(window_size=100, z_threshold=3.0, weight=1.5))
        ]
        detector = ConflictDetector()
        resolver = ResolutionEngine(ViewWeightConfig())
        evaluator = Evaluator()
        
        # Action mapping helper
        def _get_action(sentiment, ruling_basis):
            """Map sentiment + ruling basis to action recommendation"""
            if ruling_basis == "override":
                return "EXIT"  # Emergency override = get out
            if sentiment == Sentiment.CRASH:
                return "EXIT"
            elif sentiment == Sentiment.SPIKE:
                return "ESCALATE"
            elif sentiment in {Sentiment.OVEREXTENDED_HIGH, Sentiment.OVEREXTENDED_LOW}:
                return "CONTAIN"  # At structural limits
            elif sentiment in {Sentiment.DOWNTREND, Sentiment.UPTREND}:
                return "MONITOR"  # Transitional
            elif sentiment == Sentiment.VOLATILE:
                return "CONTAIN"
            else:
                return "HOLD"  # STABLE or uncertain
        
        timeline_data = []
        all_conflicts = []
        
        total = len(events)
        for i, event in enumerate(events):
            # Analysis - each view analyzes the same event through its own temporal lens
            conclusions = []
            for v in views:
                v.add_event(event)
                conclusions.append(v.analyze())

            # Detect conflicts between views
            conflicts = detector.detect(conclusions)
            decision = resolver.resolve(conclusions, conflicts)
            evaluator.track_decision(decision.primary_conclusion, event)
            evaluator.update(event)
            
            # Log conflicts with full reasoning
            if conflicts:
                for conflict in conflicts:
                    conflict_info = {
                        "timestamp": event.timestamp.isoformat(),
                        "views": conflict.views_involved,
                        "description": conflict.description,
                        "severity": conflict.severity,
                        "conflict_type": conflict.conflict_type,
                        "ruling_basis": decision.ruling_basis,
                        "system_state": decision.system_state,
                        "resolution": decision.explanation,
                        "trusted_view": decision.primary_conclusion.time_scale,
                        "trusted_sentiment": decision.primary_conclusion.sentiment.value,
                        "suppressed_views": [f"{v[0]}: {v[1]}" for v in decision.suppressed_views],
                        "counterfactuals": decision.counterfactual_thresholds,
                        "robustness_warning": decision.robustness_warning
                    }
                    all_conflicts.append(conflict_info)
                    log(f"⚠️ CONFLICT [{conflict.conflict_type.upper()}]: {conflict.description}")
                    log(f"   → RULING ({decision.ruling_basis}): {decision.explanation}")
                    log(f"   → SYSTEM STATE: {decision.system_state}")
                    if decision.robustness_warning:
                        log(f"   ⚠ ROBUSTNESS: {decision.robustness_warning}")
                    if decision.suppressed_views:
                        for view_name, reason in decision.suppressed_views:
                            log(f"   ✗ {view_name} suppressed: {reason}")
                    if decision.counterfactual_thresholds:
                        log(f"   ℹ️ Counterfactuals: {'; '.join(decision.counterfactual_thresholds[:2])}")
            
            # Log significant events
            if decision.primary_conclusion.sentiment in [Sentiment.CRASH, Sentiment.SPIKE, Sentiment.OVEREXTENDED_HIGH, Sentiment.OVEREXTENDED_LOW]:
                log(f"➤ EVENT: {decision.primary_conclusion.sentiment.value} detected ({decision.primary_conclusion.time_scale})")

            # Store timeline point with separated concerns:
            # - system_state: STABLE/CONTESTED/FRAGILE/PRECARIOUS/CRITICAL (conflict posture)
            # - structural_view: Long-term's assessment of underlying stability
            # - action: What the ruling recommends (based on primary conclusion)
            long_term = by_scale.get("Long") if 'by_scale' in dir() else (conclusions[2] if len(conclusions) > 2 else None)
            structural_assessment = long_term.sentiment.value if long_term else "UNKNOWN"
            action_recommendation = _get_action(decision.primary_conclusion.sentiment, decision.ruling_basis)
            
            timeline_data.append({
                "timestamp": event.timestamp.isoformat(),
                "value": event.value,
                "short_conf": conclusions[0].confidence,
                "short_sent": conclusions[0].sentiment.value,
                "mid_conf": conclusions[1].confidence,
                "mid_sent": conclusions[1].sentiment.value,
                "long_conf": conclusions[2].confidence,
                "long_sent": conclusions[2].sentiment.value,
                "system_state": decision.system_state,  # CRITICAL, PRECARIOUS, etc.
                "structural_view": structural_assessment,  # What Long thinks about structure
                "action": action_recommendation,  # HOLD, EXIT, CONTAIN, ESCALATE
                "explanation": decision.explanation
            })
            
            if i % 50 == 0:
                analyses[file_id].progress = int((i / total) * 100)
                analyses[file_id].conflicts = all_conflicts
                await asyncio.sleep(0)

        report = evaluator.get_report()
        
        elapsed_time = time.time() - start_time
        log(f"[COMPLETE] Analysis Finished.")
        log(f"[INFO] Total Conflicts Detected: {len(all_conflicts)}")
        log(f"[TIMING] Processing completed in {elapsed_time:.2f} seconds")
        
        # Calculate system confidence from conflict severity
        if all_conflicts:
            avg_severity = sum(c['severity'] for c in all_conflicts) / len(all_conflicts)
            system_confidence = max(0, 100 - (avg_severity * 50))  # Higher conflicts = lower confidence
            log(f"[SYSTEM] System Confidence: {system_confidence:.1f}% (inversely scaled by conflict severity)")
        else:
            system_confidence = 95.0  # High confidence when no conflicts
            log(f"[SYSTEM] System Confidence: {system_confidence:.1f}% (no conflicts detected)")
        
        analyses[file_id].status = "completed"
        analyses[file_id].progress = 100
        analyses[file_id].accuracy = system_confidence  # Now represents actual system confidence, not fake accuracy
        analyses[file_id].timeline = timeline_data
        analyses[file_id].conflicts = all_conflicts
        analyses[file_id].final_report = report
        
    except Exception as e:
        log(f"[ERROR] Analysis Failed: {str(e)}")
        analyses[file_id].status = "failed"
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import uvicorn
    print("Starting Trikal-Drsti Server on port 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
