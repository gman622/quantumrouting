import { useEffect, useState } from 'react'
import useStore from './store'
import useSolver from './hooks/useSolver'
import IntentCanvas from './components/IntentCanvas'
import ConstraintPanel from './components/ConstraintPanel'
import ViolationsDashboard from './components/ViolationsDashboard'
import LeftPanel from './components/LeftPanel'
import IntentDetail from './components/IntentDetail'
import WaveDiffPanel from './components/WaveDiffPanel'
import type { WaveData } from './types'

// Sample wave data for demo
const sampleWaveData: WaveData = {
  waveId: 'demo-1',
  intentDeltas: [
    {
      intentId: 'intent-1',
      title: 'Add user authentication',
      status: 'success',
      agent: 'Claude Code',
      agentModel: 'sonnet-4-20250506',
      changes: [
        { filePath: 'src/auth.ts', changeType: 'created', logicSummary: 'JWT token generation and validation', boilerplateSuppressed: false },
        { filePath: 'src/middleware.ts', changeType: 'modified', logicSummary: 'Auth middleware for protected routes', boilerplateSuppressed: true },
      ],
      warnings: [],
      errors: [],
    },
    {
      intentId: 'intent-2',
      title: 'Update database schema',
      status: 'warning',
      agent: 'GPT-4o',
      agentModel: 'gpt-4o-2024-08-06',
      changes: [
        { filePath: 'schema.sql', changeType: 'modified', logicSummary: 'Added user_roles table', boilerplateSuppressed: false },
        { filePath: 'migrations/002.sql', changeType: 'created', logicSummary: 'Migration script', boilerplateSuppressed: true },
      ],
      warnings: ['Potential breaking change in user table'],
      errors: [],
    },
    {
      intentId: 'intent-3',
      title: 'Fix API rate limiting',
      status: 'success',
      agent: 'DeepSeek Coder',
      agentModel: 'deepseek-coder-v2',
      changes: [
        { filePath: 'src/rate_limiter.py', changeType: 'modified', logicSummary: 'Redis-based rate limiting with sliding window', boilerplateSuppressed: false },
      ],
      warnings: [],
      errors: [],
    },
  ],
  filesChanged: 5,
  files: ['src/auth.ts', 'src/middleware.ts', 'schema.sql', 'migrations/002.sql', 'src/rate_limiter.py'],
  metricsBefore: {
    p99Latency: 245,
    avgLatency: 120,
    testCoverage: 72.5,
    tokenCost: 4250,
    chainCoherence: 0.68,
    gatePassRate: 0.82,
    dependencyCount: 156,
  },
  metricsAfter: {
    p99Latency: 198,
    avgLatency: 95,
    testCoverage: 74.2,
    tokenCost: 5890,
    chainCoherence: 0.81,
    gatePassRate: 0.89,
    dependencyCount: 162,
  },
  metricDeltas: [
    { name: 'p99 Latency', before: 245, after: 198, change: -47, changeType: 'improvement', severity: 'success' },
    { name: 'Avg Latency', before: 120, after: 95, change: -25, changeType: 'improvement', severity: 'success' },
    { name: 'Test Coverage', before: 72.5, after: 74.2, change: 1.7, changeType: 'improvement', severity: 'success' },
    { name: 'Token Cost', before: 4250, after: 5890, change: 1640, changeType: 'regression', severity: 'warning' },
    { name: 'Chain Coherence', before: 0.68, after: 0.81, change: 0.13, changeType: 'improvement', severity: 'success' },
    { name: 'Gate Pass Rate', before: 0.82, after: 0.89, change: 0.07, changeType: 'improvement', severity: 'success' },
    { name: 'Dependencies', before: 156, after: 162, change: 6, changeType: 'neutral', severity: 'info' },
  ],
  impactPredictions: [
    { filePath: 'src/auth.ts', riskLevel: 'high', predictedImpact: ['Security improvement', 'Token cost increase'], affectedMetrics: ['tokenCost', 'gatePassRate'] },
    { filePath: 'src/middleware.ts', riskLevel: 'medium', predictedImpact: ['Latency reduction'], affectedMetrics: ['p99Latency', 'avgLatency'] },
    { filePath: 'schema.sql', riskLevel: 'high', predictedImpact: ['Breaking change potential'], affectedMetrics: ['gatePassRate'] },
    { filePath: 'src/rate_limiter.py', riskLevel: 'low', predictedImpact: ['Performance improvement'], affectedMetrics: ['p99Latency', 'avgLatency'] },
  ],
}

export default function App() {
  const fetchGraph = useStore((s) => s.fetchGraph)
  const fetchAssignments = useStore((s) => s.fetchAssignments)
  const fetchAgents = useStore((s) => s.fetchAgents)
  const fetchIssues = useStore((s) => s.fetchIssues)
  const solving = useStore((s) => s.solving)
  const githubRepo = useStore((s) => s.githubRepo)
  const setGithubRepo = useStore((s) => s.setGithubRepo)

  // Wave Diff state
  const [waveDiffOpen, setWaveDiffOpen] = useState(false)
  const [waveData, setWaveData] = useState<WaveData | null>(null)
  const [settingsOpen, setSettingsOpen] = useState(false)

  // Connect WebSocket
  useSolver()

  // Initial data load
  useEffect(() => {
    fetchGraph(0)
    fetchAssignments()
    fetchAgents()
    fetchIssues()
  }, [fetchGraph, fetchAssignments, fetchAgents, fetchIssues])

  return (
    <div className="h-screen w-screen flex flex-col bg-slate-900 text-slate-200 overflow-hidden">
      {/* Header */}
      <header className="h-10 bg-slate-800/80 border-b border-slate-700 flex items-center px-4 shrink-0">
        <h1 className="text-sm font-bold tracking-wider text-slate-300">
          INTENT IDE
        </h1>
        <span className="ml-3 text-xs text-slate-500">
          10K intents / CP-SAT solver / QAAS
        </span>
        {solving && (
          <span className="ml-auto text-xs text-indigo-400 flex items-center gap-2">
            <div className="w-2 h-2 bg-indigo-400 rounded-full animate-pulse" />
            Solving...
          </span>
        )}
        <button
          onClick={() => {
            setWaveData(sampleWaveData)
            setWaveDiffOpen(true)
          }}
          className="ml-4 px-3 py-1 bg-indigo-600 hover:bg-indigo-500 text-white text-xs rounded transition-colors"
        >
          Wave Diff Demo
        </button>
        <button
          onClick={() => setSettingsOpen(true)}
          className="ml-4 px-3 py-1 bg-slate-700 hover:bg-slate-600 text-slate-300 text-xs rounded transition-colors"
        >
          ⚙️ Settings
        </button>
      </header>

      {/* Main content area */}
      <div className="flex flex-1 min-h-0">
        {/* Left: Issues & Agents */}
        <LeftPanel />

        {/* Center: Canvas */}
        <main className="flex-1 relative">
          <IntentCanvas />
          <IntentDetail />
        </main>

        {/* Right: Constraint panel */}
        <ConstraintPanel />
      </div>

      {/* Bottom: Violations dashboard */}
      <ViolationsDashboard />

      {/* Wave Diff Modal */}
      {waveData && (
        <WaveDiffPanel
          waveId="demo-1"
          waveData={waveData}
          isOpen={waveDiffOpen}
          onClose={() => setWaveDiffOpen(false)}
          onRejectIntent={(id, reason) => console.log('Reject:', id, reason)}
          onRevertWave={(id) => console.log('Revert:', id)}
        />
      )}

      {/* Settings Modal */}
      {settingsOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center">
          <div className="bg-slate-800 rounded-lg p-6 w-96 border border-slate-700">
            <h2 className="text-lg font-semibold text-slate-200 mb-4">Settings</h2>
            <div className="mb-4">
              <label className="block text-sm text-slate-400 mb-2">GitHub Repository</label>
              <input
                type="text"
                value={githubRepo}
                onChange={(e) => setGithubRepo(e.target.value)}
                placeholder="owner/repo (e.g., facebook/react)"
                className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded text-slate-200 text-sm focus:outline-none focus:border-indigo-500"
              />
              <p className="text-xs text-slate-500 mt-1">
                Leave empty to use the current git repository
              </p>
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setSettingsOpen(false)}
                className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm rounded transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
