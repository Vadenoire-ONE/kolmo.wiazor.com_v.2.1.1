#!/usr/bin/env python
"""
DTKT System Connector
=====================

Standalone program to connect and manage DTKT system projects:
  - rates_winners (Python/FastAPI backend)
  - kolmo_analysis (React/Plotly frontend)

Usage:
    python dtkt_connector.py --help
    python dtkt_connector.py start-api
    python dtkt_connector.py start-ui
    python dtkt_connector.py start-all
    python dtkt_connector.py init-analysis
    python dtkt_connector.py status

Author: DTKT Architecture Team
Version: 2.1.1
"""

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ============================================================================
# Configuration
# ============================================================================

@dataclass
class DTKTConfig:
    """Configuration for DTKT system projects."""
    
    # Project paths (relative to this script)
    rates_winners_dir: Path = field(default_factory=lambda: Path(__file__).parent)
    kolmo_analysis_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent / "kolmo_analysis")
    
    # API settings
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_reload: bool = True
    
    # UI settings
    ui_port: int = 5173
    
    # Endpoints
    @property
    def api_base_url(self) -> str:
        return f"http://{self.api_host}:{self.api_port}"
    
    @property
    def api_winner_url(self) -> str:
        return f"{self.api_base_url}/api/v1/winner/latest"
    
    @property
    def api_rates_url(self) -> str:
        return f"{self.api_base_url}/api/v1/rates"
    
    @property
    def api_health_url(self) -> str:
        return f"{self.api_base_url}/api/v1/health"


# ============================================================================
# Process Management
# ============================================================================

class ProcessManager:
    """Manages subprocesses for API and UI servers."""
    
    def __init__(self, config: DTKTConfig):
        self.config = config
        self.processes: dict[str, subprocess.Popen] = {}
    
    def start_api(self) -> bool:
        """Start the rates_winners FastAPI server."""
        print(f"🚀 Starting rates_winners API on {self.config.api_base_url}...")
        
        cmd = [
            sys.executable, "-m", "uvicorn",
            "kolmo.main:app",
            "--host", self.config.api_host,
            "--port", str(self.config.api_port),
        ]
        
        if self.config.api_reload:
            cmd.append("--reload")
        
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(self.config.rates_winners_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            self.processes["api"] = proc
            print(f"✅ API server started (PID: {proc.pid})")
            print(f"   OpenAPI docs: {self.config.api_base_url}/docs")
            return True
        except Exception as e:
            print(f"❌ Failed to start API: {e}")
            return False
    
    def start_ui(self) -> bool:
        """Start the kolmo_analysis Vite dev server."""
        analysis_dir = self.config.kolmo_analysis_dir
        
        if not analysis_dir.exists():
            print(f"❌ kolmo_analysis directory not found: {analysis_dir}")
            print("   Run 'python dtkt_connector.py init-analysis' first.")
            return False
        
        print(f"🎨 Starting kolmo_analysis UI on http://localhost:{self.config.ui_port}...")
        
        # Determine npm command based on OS
        npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
        
        cmd = [npm_cmd, "run", "dev", "--", "--port", str(self.config.ui_port)]
        
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(analysis_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                shell=(sys.platform == "win32"),
            )
            self.processes["ui"] = proc
            print(f"✅ UI server started (PID: {proc.pid})")
            return True
        except Exception as e:
            print(f"❌ Failed to start UI: {e}")
            return False
    
    def stop_all(self):
        """Stop all managed processes."""
        for name, proc in self.processes.items():
            if proc.poll() is None:
                print(f"🛑 Stopping {name} (PID: {proc.pid})...")
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
        self.processes.clear()
    
    def stream_output(self):
        """Stream output from all processes."""
        import select
        
        while self.processes:
            for name, proc in list(self.processes.items()):
                if proc.poll() is not None:
                    print(f"⚠️  {name} process exited with code {proc.returncode}")
                    del self.processes[name]
                    continue
                
                if proc.stdout:
                    line = proc.stdout.readline()
                    if line:
                        prefix = "🔵 API" if name == "api" else "🟢 UI "
                        print(f"{prefix} | {line.rstrip()}")
            
            time.sleep(0.1)


# ============================================================================
# Project Initialization
# ============================================================================

def init_kolmo_analysis(config: DTKTConfig, force: bool = False) -> bool:
    """
    Initialize the kolmo_analysis React project with Plotly integration.
    
    Creates a Vite + React + TypeScript project configured to consume
    the rates_winners API.
    """
    analysis_dir = config.kolmo_analysis_dir
    
    if analysis_dir.exists() and not force:
        print(f"⚠️  Directory already exists: {analysis_dir}")
        print("   Use --force to overwrite.")
        return False
    
    print(f"📦 Initializing kolmo_analysis project at {analysis_dir}...")
    
    # Create directory structure
    analysis_dir.mkdir(parents=True, exist_ok=True)
    
    # Create package.json
    package_json = {
        "name": "kolmo-analysis",
        "version": "2.1.1",
        "private": True,
        "type": "module",
        "scripts": {
            "dev": "vite",
            "build": "tsc && vite build",
            "preview": "vite preview",
            "lint": "eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0"
        },
        "dependencies": {
            "react": "^18.2.0",
            "react-dom": "^18.2.0",
            "plotly.js-dist-min": "^2.27.0",
            "lucide-react": "^0.263.1"
        },
        "devDependencies": {
            "@types/react": "^18.2.0",
            "@types/react-dom": "^18.2.0",
            "@vitejs/plugin-react": "^4.0.0",
            "typescript": "^5.0.0",
            "vite": "^5.0.0"
        }
    }
    
    (analysis_dir / "package.json").write_text(
        json.dumps(package_json, indent=2), encoding="utf-8"
    )
    
    # Create vite.config.ts
    vite_config = '''import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  }
})
'''
    (analysis_dir / "vite.config.ts").write_text(vite_config, encoding="utf-8")
    
    # Create tsconfig.json
    tsconfig = {
        "compilerOptions": {
            "target": "ES2020",
            "useDefineForClassFields": True,
            "lib": ["ES2020", "DOM", "DOM.Iterable"],
            "module": "ESNext",
            "skipLibCheck": True,
            "moduleResolution": "bundler",
            "allowImportingTsExtensions": True,
            "resolveJsonModule": True,
            "isolatedModules": True,
            "noEmit": True,
            "jsx": "react-jsx",
            "strict": True,
            "noUnusedLocals": True,
            "noUnusedParameters": True,
            "noFallthroughCasesInSwitch": True
        },
        "include": ["src"],
        "references": [{"path": "./tsconfig.node.json"}]
    }
    (analysis_dir / "tsconfig.json").write_text(
        json.dumps(tsconfig, indent=2), encoding="utf-8"
    )
    
    # Create tsconfig.node.json
    tsconfig_node = {
        "compilerOptions": {
            "composite": True,
            "skipLibCheck": True,
            "module": "ESNext",
            "moduleResolution": "bundler",
            "allowSyntheticDefaultImports": True
        },
        "include": ["vite.config.ts"]
    }
    (analysis_dir / "tsconfig.node.json").write_text(
        json.dumps(tsconfig_node, indent=2), encoding="utf-8"
    )
    
    # Create index.html
    index_html = '''<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>KOLMO Analysis - DTKT System</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
'''
    (analysis_dir / "index.html").write_text(index_html, encoding="utf-8")
    
    # Create src directory
    src_dir = analysis_dir / "src"
    src_dir.mkdir(exist_ok=True)
    
    # Create main.tsx
    main_tsx = '''import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
'''
    (src_dir / "main.tsx").write_text(main_tsx, encoding="utf-8")
    
    # Create index.css
    index_css = '''* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen,
    Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
  background-color: #f8fafc;
  color: #1e293b;
}

.container {
  max-width: 1400px;
  margin: 0 auto;
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.title {
  font-size: 24px;
  font-weight: 600;
  color: #0f172a;
}

.subtitle {
  font-size: 14px;
  color: #64748b;
}

.card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  padding: 20px;
  margin-bottom: 20px;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.metric-card {
  background: white;
  border-radius: 8px;
  padding: 16px;
  border: 1px solid #e2e8f0;
}

.metric-label {
  font-size: 12px;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.metric-value {
  font-size: 24px;
  font-weight: 600;
  color: #0f172a;
  margin-top: 4px;
}

.winner-badge {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 9999px;
  font-size: 14px;
  font-weight: 500;
}

.winner-iou2 { background: #dbeafe; color: #1d4ed8; }
.winner-me4u { background: #fef3c7; color: #d97706; }
.winner-uome { background: #d1fae5; color: #059669; }

.status-ok { color: #059669; }
.status-warn { color: #d97706; }
.status-critical { color: #dc2626; }

.chart-container {
  width: 100%;
  height: 500px;
}

.loading {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 200px;
  color: #64748b;
}

.error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #dc2626;
  padding: 16px;
  border-radius: 8px;
}
'''
    (src_dir / "index.css").write_text(index_css, encoding="utf-8")
    
    # Create App.tsx with KOLMO API integration
    app_tsx = '''import { useState, useEffect, useRef } from 'react'
import Plotly from 'plotly.js-dist-min'
import { RefreshCw, TrendingUp, AlertTriangle, CheckCircle } from 'lucide-react'

// ============================================================================
// Types (matching rates_winners API schemas)
// ============================================================================

interface WinnerReason {
  me4u_relpath: number | null
  iou2_relpath: number | null
  uome_relpath: number | null
  max_relpath: number | null
  tied_coins: string[]
  selection_rule: string
  winner: string
}

interface WinnerResponse {
  date: string
  winner: 'IOU2' | 'ME4U' | 'UOME'
  kolmo_value_str: string
  kolmo_value: number
  r_me4u: string
  r_iou2: string
  r_uome: string
  kolmo_deviation: number
  kolmo_state: 'OK' | 'WARN' | 'CRITICAL'
  winner_reason: WinnerReason
  dist_me4u: number | null
  dist_iou2: number | null
  dist_uome: number | null
  relpath_me4u: number | null
  relpath_iou2: number | null
  relpath_uome: number | null
}

interface HealthResponse {
  status: string
  version: string
  database: string
  latest_data_date: string | null
  data_freshness_hours: number | null
}

// ============================================================================
// API Client
// ============================================================================

const API_BASE = '/api/v1'

async function fetchLatestWinner(): Promise<WinnerResponse> {
  const res = await fetch(`${API_BASE}/winner/latest`)
  if (!res.ok) {
    throw new Error(`API error: ${res.status}`)
  }
  return res.json()
}

async function fetchRatesByDate(date: string): Promise<WinnerResponse> {
  const res = await fetch(`${API_BASE}/rates/${date}`)
  if (!res.ok) {
    throw new Error(`API error: ${res.status}`)
  }
  return res.json()
}

async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/health`)
  if (!res.ok) {
    throw new Error(`API error: ${res.status}`)
  }
  return res.json()
}

// ============================================================================
// Components
// ============================================================================

function MetricCard({ 
  label, 
  value, 
  suffix = '', 
  className = '' 
}: { 
  label: string
  value: string | number
  suffix?: string
  className?: string
}) {
  return (
    <div className="metric-card">
      <div className="metric-label">{label}</div>
      <div className={`metric-value ${className}`}>
        {value}{suffix}
      </div>
    </div>
  )
}

function WinnerBadge({ winner }: { winner: string }) {
  const className = `winner-badge winner-${winner.toLowerCase()}`
  return <span className={className}>{winner}</span>
}

function StatusIcon({ state }: { state: string }) {
  switch (state) {
    case 'OK':
      return <CheckCircle className="status-ok" size={20} />
    case 'WARN':
      return <AlertTriangle className="status-warn" size={20} />
    case 'CRITICAL':
      return <AlertTriangle className="status-critical" size={20} />
    default:
      return null
  }
}

// ============================================================================
// Main App
// ============================================================================

export default function App() {
  const [data, setData] = useState<WinnerResponse | null>(null)
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const chartRef = useRef<HTMLDivElement>(null)

  const loadData = async () => {
    setLoading(true)
    setError(null)
    try {
      const [winnerData, healthData] = await Promise.all([
        fetchLatestWinner(),
        fetchHealth()
      ])
      setData(winnerData)
      setHealth(healthData)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  // Render Plotly chart when data changes
  useEffect(() => {
    if (!chartRef.current || !data) return

    const traces = [
      {
        type: 'indicator',
        mode: 'gauge+number+delta',
        value: data.kolmo_deviation,
        title: { text: 'KOLMO Deviation (%)' },
        delta: { reference: 0 },
        gauge: {
          axis: { range: [0, 5], ticksuffix: '%' },
          bar: { color: data.kolmo_state === 'OK' ? '#059669' : 
                        data.kolmo_state === 'WARN' ? '#d97706' : '#dc2626' },
          steps: [
            { range: [0, 1], color: '#d1fae5' },
            { range: [1, 5], color: '#fef3c7' },
          ],
          threshold: {
            line: { color: '#dc2626', width: 4 },
            thickness: 0.75,
            value: 5
          }
        },
        domain: { x: [0, 0.45], y: [0, 1] }
      },
      {
        type: 'indicator',
        mode: 'number',
        value: Number(data.kolmo_value_str),
        title: { text: 'KOLMO Invariant (K)' },
        number: { 
          valueformat: '.18f',
          font: { size: 20 }
        },
        domain: { x: [0.55, 1], y: [0.5, 1] }
      }
    ]

    const layout = {
      height: 300,
      margin: { t: 50, b: 20, l: 30, r: 30 },
      paper_bgcolor: 'rgba(0,0,0,0)',
      font: { family: 'inherit' }
    }

    Plotly.newPlot(chartRef.current, traces as any, layout as any, { 
      responsive: true,
      displayModeBar: false 
    })

    return () => {
      if (chartRef.current) {
        Plotly.purge(chartRef.current)
      }
    }
  }, [data])

  if (loading) {
    return (
      <div className="container">
        <div className="loading">Loading KOLMO data...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="container">
        <div className="error">
          <strong>Error:</strong> {error}
          <br />
          <small>Make sure rates_winners API is running on port 8000.</small>
        </div>
      </div>
    )
  }

  if (!data) return null

  return (
    <div className="container">
      <div className="header">
        <div>
          <h1 className="title">KOLMO Analysis</h1>
          <p className="subtitle">
            DTKT Currency Triangle Monitoring • v{health?.version || '2.1.1'}
          </p>
        </div>
        <button 
          onClick={loadData}
          style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: 8,
            padding: '8px 16px',
            borderRadius: 8,
            border: '1px solid #e2e8f0',
            background: 'white',
            cursor: 'pointer'
          }}
        >
          <RefreshCw size={16} />
          Refresh
        </button>
      </div>

      {/* Winner Card */}
      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
          <TrendingUp size={24} />
          <div>
            <div style={{ fontSize: 14, color: '#64748b' }}>Today's Winner ({data.date})</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <WinnerBadge winner={data.winner} />
              <StatusIcon state={data.kolmo_state} />
              <span style={{ fontSize: 14, color: '#64748b' }}>
                {data.kolmo_state}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="metrics-grid">
        <MetricCard label="ME4U Rate (USD/CNY)" value={data.r_me4u} />
        <MetricCard label="IOU2 Rate (EUR/USD)" value={data.r_iou2} />
        <MetricCard label="UOME Rate (CNY/EUR)" value={data.r_uome} />
        <MetricCard 
          label="KOLMO Deviation" 
          value={data.kolmo_deviation.toFixed(4)} 
          suffix="%"
          className={`status-${data.kolmo_state.toLowerCase()}`}
        />
      </div>

      {/* RelativePath Metrics */}
      <div className="card">
        <h3 style={{ marginBottom: 16 }}>RelativePath Metrics</h3>
        <div className="metrics-grid">
          <MetricCard 
            label="ME4U RelPath" 
            value={data.relpath_me4u?.toFixed(4) ?? 'N/A'} 
          />
          <MetricCard 
            label="IOU2 RelPath" 
            value={data.relpath_iou2?.toFixed(4) ?? 'N/A'} 
          />
          <MetricCard 
            label="UOME RelPath" 
            value={data.relpath_uome?.toFixed(4) ?? 'N/A'} 
          />
        </div>
      </div>

      {/* Plotly Chart */}
      <div className="card">
        <h3 style={{ marginBottom: 16 }}>KOLMO Invariant Gauge</h3>
        <div ref={chartRef} className="chart-container" style={{ height: 300 }} />
      </div>

      {/* Winner Reason */}
      <div className="card">
        <h3 style={{ marginBottom: 16 }}>Winner Selection Reason</h3>
        <pre style={{ 
          background: '#f1f5f9', 
          padding: 16, 
          borderRadius: 8,
          overflow: 'auto',
          fontSize: 13
        }}>
          {JSON.stringify(data.winner_reason, null, 2)}
        </pre>
      </div>
    </div>
  )
}
'''
    (src_dir / "App.tsx").write_text(app_tsx, encoding="utf-8")
    
    # Copy example components if they exist
    example_dir = config.rates_winners_dir / "example"
    if example_dir.exists():
        components_src = example_dir / "components"
        if components_src.exists():
            components_dst = src_dir / "components"
            if components_dst.exists():
                shutil.rmtree(components_dst)
            shutil.copytree(components_src, components_dst)
            print("   ✅ Copied components from example/")
    
    print(f"✅ kolmo_analysis project initialized at {analysis_dir}")
    print("")
    print("Next steps:")
    print(f"  1. cd {analysis_dir}")
    print("  2. npm install")
    print("  3. npm run dev")
    print("")
    print("Or use: python dtkt_connector.py start-all")
    
    return True


# ============================================================================
# Status Check
# ============================================================================

def check_status(config: DTKTConfig):
    """Check status of DTKT system components."""
    import urllib.request
    import urllib.error
    
    print("🔍 DTKT System Status Check")
    print("=" * 50)
    
    # Check rates_winners directory
    print(f"\n📂 rates_winners: {config.rates_winners_dir}")
    if config.rates_winners_dir.exists():
        print("   ✅ Directory exists")
        if (config.rates_winners_dir / "src" / "kolmo").exists():
            print("   ✅ Python package found")
        else:
            print("   ❌ Python package not found")
    else:
        print("   ❌ Directory not found")
    
    # Check kolmo_analysis directory
    print(f"\n📂 kolmo_analysis: {config.kolmo_analysis_dir}")
    if config.kolmo_analysis_dir.exists():
        print("   ✅ Directory exists")
        if (config.kolmo_analysis_dir / "package.json").exists():
            print("   ✅ package.json found")
        else:
            print("   ⚠️  package.json not found")
        if (config.kolmo_analysis_dir / "node_modules").exists():
            print("   ✅ node_modules installed")
        else:
            print("   ⚠️  Run 'npm install' in kolmo_analysis/")
    else:
        print("   ❌ Directory not found")
        print("   💡 Run: python dtkt_connector.py init-analysis")
    
    # Check API health
    print(f"\n🌐 API Health: {config.api_health_url}")
    try:
        with urllib.request.urlopen(config.api_health_url, timeout=5) as response:
            data = json.loads(response.read())
            print(f"   ✅ Status: {data.get('status', 'unknown')}")
            print(f"   ✅ Version: {data.get('version', 'unknown')}")
            print(f"   ✅ Database: {data.get('database', 'unknown')}")
            if data.get('latest_data_date'):
                print(f"   ✅ Latest data: {data['latest_data_date']}")
    except urllib.error.URLError:
        print("   ❌ API not responding")
        print("   💡 Run: python dtkt_connector.py start-api")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("\n" + "=" * 50)


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="DTKT System Connector - Manage rates_winners and kolmo_analysis projects",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python dtkt_connector.py status          Check system status
  python dtkt_connector.py init-analysis   Initialize kolmo_analysis project
  python dtkt_connector.py start-api       Start rates_winners API server
  python dtkt_connector.py start-ui        Start kolmo_analysis dev server
  python dtkt_connector.py start-all       Start both servers

Environment:
  API runs on http://localhost:8000
  UI runs on http://localhost:5173 (with proxy to API)
        """
    )
    
    parser.add_argument(
        "command",
        choices=["status", "init-analysis", "start-api", "start-ui", "start-all"],
        help="Command to execute"
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force overwrite existing files (for init-analysis)"
    )
    
    parser.add_argument(
        "--api-port",
        type=int,
        default=8000,
        help="API server port (default: 8000)"
    )
    
    parser.add_argument(
        "--ui-port",
        type=int,
        default=5173,
        help="UI dev server port (default: 5173)"
    )
    
    args = parser.parse_args()
    
    config = DTKTConfig()
    config.api_port = args.api_port
    config.ui_port = args.ui_port
    
    if args.command == "status":
        check_status(config)
    
    elif args.command == "init-analysis":
        init_kolmo_analysis(config, force=args.force)
    
    elif args.command == "start-api":
        manager = ProcessManager(config)
        
        def signal_handler(sig, frame):
            print("\n🛑 Shutting down...")
            manager.stop_all()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        
        if manager.start_api():
            manager.stream_output()
    
    elif args.command == "start-ui":
        manager = ProcessManager(config)
        
        def signal_handler(sig, frame):
            print("\n🛑 Shutting down...")
            manager.stop_all()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        
        if manager.start_ui():
            manager.stream_output()
    
    elif args.command == "start-all":
        manager = ProcessManager(config)
        
        def signal_handler(sig, frame):
            print("\n🛑 Shutting down...")
            manager.stop_all()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        
        print("🚀 Starting DTKT System...")
        print("")
        
        api_ok = manager.start_api()
        if api_ok:
            time.sleep(2)  # Wait for API to start
        
        ui_ok = manager.start_ui()
        
        if api_ok or ui_ok:
            print("")
            print("=" * 50)
            print("DTKT System Running:")
            if api_ok:
                print(f"  🔵 API:  {config.api_base_url}")
                print(f"     Docs: {config.api_base_url}/docs")
            if ui_ok:
                print(f"  🟢 UI:   http://localhost:{config.ui_port}")
            print("=" * 50)
            print("Press Ctrl+C to stop all services")
            print("")
            
            manager.stream_output()


if __name__ == "__main__":
    main()
