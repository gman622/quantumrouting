import { useEffect } from 'react'
import useStore from './store'
import useSolver from './hooks/useSolver'
import IntentCanvas from './components/IntentCanvas'
import ConstraintPanel from './components/ConstraintPanel'
import ViolationsDashboard from './components/ViolationsDashboard'
import LeftPanel from './components/LeftPanel'
import IntentDetail from './components/IntentDetail'

export default function App() {
  const fetchGraph = useStore((s) => s.fetchGraph)
  const fetchAssignments = useStore((s) => s.fetchAssignments)
  const fetchAgents = useStore((s) => s.fetchAgents)
  const fetchIssues = useStore((s) => s.fetchIssues)
  const solving = useStore((s) => s.solving)

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
    </div>
  )
}
