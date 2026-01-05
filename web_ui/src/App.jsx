import { useState, useEffect, useRef } from 'react'
import './App.css'

const API_URL = "http://localhost:8000";

function App() {
  const [file, setFile] = useState(null);
  const [status, setStatus] = useState("IDLE"); // IDLE, UPLOADING, PROCESSING, COMPLETED, FAILED
  const [logs, setLogs] = useState([]);
  const [timeline, setTimeline] = useState([]);
  const [conflicts, setConflicts] = useState([]);
  const [analysisId, setAnalysisId] = useState(null);
  const [finalReport, setFinalReport] = useState(null);
  const [systemConfidence, setSystemConfidence] = useState(null);
  const terminalEndRef = useRef(null);
  const fileInputRef = useRef(null);

  // Auto-scroll terminal
  useEffect(() => {
    terminalEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  // Polling Effect
  useEffect(() => {
    let interval;
    if (status === "PROCESSING" && analysisId) {
      interval = setInterval(async () => {
        try {
          const res = await fetch(`${API_URL}/analysis/${analysisId}`);
          const data = await res.json();

          if (data.status) {
            setLogs(data.logs || []);
            setTimeline(data.timeline || []);
            setConflicts(data.conflicts || []);
            setSystemConfidence(data.accuracy || null);

            if (data.status === "completed") {
              setStatus("COMPLETED");
              if (data.final_report) {
                setFinalReport(data.final_report);
              }
              clearInterval(interval);
            }
            if (data.status === "failed") {
              setStatus("FAILED");
              clearInterval(interval);
            }
          }
        } catch (e) {
          console.error("Polling error", e);
          setLogs(prev => [...prev, `[ERROR] Polling failed: ${e.message}`]);
        }
      }, 500); // Poll every 500ms
    }
    return () => clearInterval(interval);
  }, [status, analysisId]);

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setStatus("UPLOADING");
    setLogs(["[SYSTEM] Initiating Upload Sequence..."]);
    setTimeline([]);
    setConflicts([]);
    setFinalReport(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${API_URL}/upload`, {
        method: "POST",
        body: formData,
      });
      
      if (!res.ok) {
        const errorText = await res.text();
        setStatus("FAILED");
        setLogs(prev => [...prev, `[ERROR] Server returned ${res.status}: ${errorText.substring(0, 200)}`]);
        return;
      }

      const data = await res.json();
      
      setLogs(prev => [...prev, `[INFO] Upload successful. ID: ${data.id}`]);

      if (data.id) {
        setAnalysisId(data.id);
        if (data.is_video) {
          setStatus("COMPLETED");
          setLogs(prev => [...prev, "[SYSTEM] Video Detected.", `[INFO] ${data.message}`]);
        } else {
          setStatus("PROCESSING");
          setLogs(prev => [...prev, "[SYSTEM] Processing data..."]);
        }
      } else {
        setStatus("FAILED");
        setLogs(prev => [...prev, "[ERROR] Upload failed. No ID returned."]);
      }
    } catch (e) {
      setStatus("FAILED");
      setLogs(prev => [...prev, `[CRITICAL] Connection Error: ${e.message}`]);
    }
  };

  const getLogClass = (text) => {
    if (text.includes("ERROR") || text.includes("CRASH")) return "red";
    if (text.includes("CONFLICT") || text.includes("WARNING")) return "yellow";
    if (text.includes("EVENT")) return "cyan";
    if (text.includes("COMPLETE")) return "green";
    return "";
  };

  // derived stats
  const lastPoint = timeline.length > 0 ? timeline[timeline.length - 1] : null;
  const currentSentiment = lastPoint ? lastPoint.sentiment : "WAITING";
  const systemState = lastPoint ? lastPoint.system_state : "STABLE";
  const confidence = lastPoint ? Math.round(lastPoint.mid_conf * 100) : 0;

  return (
    <div className="main-wrapper">
      <div className="title">Trikal-Drsti Engine v2.0</div>

      <div className="container">

        {/* LEFT PANEL: INPUT & LOGS */}
        <div className="panel">
          <div className="panel-header"><div>INPUT MODULE</div><div>STATUS: {status}</div></div>

          <div
            className="drop-zone"
            onDragOver={handleDragOver}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current.click()}
          >
            <input
              type="file"
              hidden
              ref={fileInputRef}
              onChange={(e) => setFile(e.target.files[0])}
            />
            {file ? (
              <div style={{ color: 'var(--neon-cyan)' }}>{file.name}</div>
            ) : (
              <>
                <div style={{ fontSize: '2rem' }}>+</div>
                <div>DROP DATASET [CSV/JSON/MP4]</div>
              </>
            )}
          </div>

          <button
            onClick={handleUpload}
            disabled={status === "UPLOADING" || status === "PROCESSING" || !file}
            style={{
              background: 'transparent',
              border: '1px solid var(--neon-cyan)',
              color: 'var(--neon-cyan)',
              padding: '10px',
              fontFamily: 'Orbitron',
              cursor: 'pointer',
              marginBottom: '20px'
            }}
          >
            {status === "PROCESSING" ? "ANALYZING STREAM..." : "INITIATE SEQUENCE"}
          </button>

          <div className="panel-header"><div>SYSTEM LOGS</div></div>
          <div className="terminal">
            {logs.map((log, i) => (
              <div key={i} className={`log-entry ${getLogClass(log)}`}>{log}</div>
            ))}
            <div ref={terminalEndRef} />
          </div>
        </div>

        {/* RIGHT PANEL: VISUALIZATION */}
        <div className="panel">
          <div className="panel-header">
            <div>TEMPORAL ANALYSIS STREAM</div>
            <div className={currentSentiment === "CRASH" ? "blink" : ""}>
              STATE: {systemState}
              {systemState !== "STABLE" && (
                <span style={{fontSize: '0.7rem', color: systemState === 'CRITICAL' ? 'red' : systemState === 'PRECARIOUS' ? 'orange' : 'yellow', marginLeft: '8px'}}>
                  {currentSentiment}
                </span>
              )}
            </div>
          </div>

          <div className="hud-grid">
            <div className="hud-card">
              <div className="hud-label">SYS CONFIDENCE</div>
              <div className="hud-val" style={{ color: systemConfidence ? 
                (systemConfidence < 50 ? 'red' : systemConfidence >= 75 ? '#00ff00' : 'var(--neon-cyan)') 
                : 'gray' }}>
                {systemConfidence ? `${Math.round(systemConfidence)}%` : '---'}
              </div>
              <div style={{fontSize: '0.6rem', color: 'gray', marginTop: '2px'}}>conflict-scaled</div>
            </div>
            <div className="hud-card">
              <div className="hud-label">CONFIDENCE (MID)</div>
              <div className="hud-val" style={{ color: confidence < 50 ? 'red' : 'inherit' }}>{confidence}%</div>
            </div>
            <div className="hud-card">
              <div className="hud-label">EVENTS</div>
              <div className="hud-val">{timeline.length}</div>
            </div>
            <div className="hud-card">
              <div className="hud-label">CONFLICTS</div>
              <div className="hud-val" style={{ color: conflicts.length > 0 ? 'var(--neon-yellow)' : 'inherit' }}>{conflicts.length}</div>
            </div>
          </div>

          {/* Conflicts Panel */}
          {conflicts.length > 0 && (
            <>
              <div className="panel-header" style={{ marginTop: '15px' }}><div>⚠ TEMPORAL CONFLICTS</div></div>
              <div className="conflicts-window">
                {conflicts.slice(-5).reverse().map((c, i) => (
                  <div key={i} className="conflict-card">
                    <div className="conflict-header">
                      <span className="conflict-views">{c.views.join(' ↔ ')}</span>
                      <span className="conflict-severity" style={{ color: c.severity > 0.5 ? 'red' : 'yellow' }}>
                        SEV: {(c.severity * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="conflict-desc">{c.description}</div>
                    <div className="conflict-resolution">
                      → TRUSTED: <span style={{ color: 'var(--neon-cyan)' }}>{c.trusted_view}</span> ({c.trusted_sentiment})
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          <div className="panel-header" style={{ marginTop: '15px' }}><div>MULTI-SCALE TIMELINE</div></div>
          <div className="analysis-window">
            <div className="timeline-row timeline-header">
              <div style={{ width: '12%' }}>TIME</div>
              <div style={{ width: '8%' }}>VALUE</div>
              <div style={{ width: '16%' }}>SHORT</div>
              <div style={{ width: '16%' }}>MID</div>
              <div style={{ width: '16%' }}>LONG</div>
              <div style={{ width: '10%' }}>POSTURE</div>
              <div style={{ width: '11%' }}>STRUCTURE</div>
              <div style={{ width: '11%' }}>ACTION</div>
            </div>
            {timeline.slice().reverse().slice(0, 50).map((pt, i) => (
              <div key={i} className="timeline-row">
                <div style={{ width: '12%' }}>{pt.timestamp.split('T')[1]?.substring(0,5) || pt.timestamp.substring(11,16)}</div>
                <div style={{ width: '8%' }}>{pt.value.toFixed(1)}</div>
                <div style={{ width: '16%', color: pt.short_sent === 'CRASH' ? 'red' : pt.short_sent === 'SPIKE' ? 'green' : 'inherit' }}>
                  {pt.short_sent || 'STABLE'} <span style={{opacity: 0.6}}>({(pt.short_conf*100).toFixed(0)}%)</span>
                </div>
                <div style={{ width: '16%', color: pt.mid_sent === 'DOWNTREND' ? 'red' : pt.mid_sent === 'UPTREND' ? 'green' : 'inherit' }}>
                  {pt.mid_sent || 'STABLE'} <span style={{opacity: 0.6}}>({(pt.mid_conf*100).toFixed(0)}%)</span>
                </div>
                <div style={{ width: '16%', color: pt.long_sent?.includes('OVEREXTENDED') ? 'yellow' : 'inherit' }}>
                  {pt.long_sent || 'STABLE'} <span style={{opacity: 0.6}}>({(pt.long_conf*100).toFixed(0)}%)</span>
                </div>
                <div style={{ width: '10%', color: 
                  pt.system_state === 'CRITICAL' ? 'red' : 
                  pt.system_state === 'PRECARIOUS' ? 'orange' :
                  pt.system_state === 'FRAGILE' ? 'yellow' :
                  pt.system_state === 'CONTESTED' ? 'var(--neon-cyan)' : 
                  'inherit' 
                }}>
                  {pt.system_state || 'STABLE'}
                </div>
                <div style={{ width: '11%', color: pt.structural_view?.includes('OVEREXTENDED') ? 'yellow' : 'inherit' }}>
                  {pt.structural_view || 'STABLE'}
                </div>
                <div style={{ width: '11%', color: 
                  pt.action === 'EXIT' ? 'red' : 
                  pt.action === 'ESCALATE' ? 'orange' :
                  pt.action === 'CONTAIN' ? 'yellow' : 
                  pt.action === 'MONITOR' ? 'var(--neon-cyan)' :
                  'inherit' 
                }}>
                  {pt.action || 'HOLD'}
                </div>
              </div>
            ))}
          </div>
        </div>

      </div>
    </div>
  )
}

export default App
