import useStore from '../store'
import IssuesPanel from './IssuesPanel'
import AgentDispatch from './AgentDispatch'

export default function LeftPanel() {
  const leftPanelTab = useStore((s) => s.leftPanelTab)
  const setLeftPanelTab = useStore((s) => s.setLeftPanelTab)
  const leftPanelOpen = useStore((s) => s.leftPanelOpen)
  const setLeftPanelOpen = useStore((s) => s.setLeftPanelOpen)
  const issues = useStore((s) => s.issues)
  const agentSummary = useStore((s) => s.agentSummary)

  return (
    <div
      className={`bg-slate-800/90 border-r border-slate-700 transition-all duration-300 overflow-hidden flex flex-col ${
        leftPanelOpen ? 'w-64' : 'w-8'
      }`}
    >
      {/* Toggle button */}
      <button
        onClick={() => setLeftPanelOpen(!leftPanelOpen)}
        className="w-full py-2 text-slate-500 hover:text-slate-300 text-xs border-b border-slate-700"
      >
        {leftPanelOpen ? '<' : '>'}
      </button>

      {leftPanelOpen && (
        <>
          {/* Tabs */}
          <div className="flex border-b border-slate-700">
            <button
              onClick={() => setLeftPanelTab('issues')}
              className={`flex-1 py-2 text-xs font-medium transition-colors ${
                leftPanelTab === 'issues'
                  ? 'text-indigo-400 border-b-2 border-indigo-400'
                  : 'text-slate-500 hover:text-slate-300'
              }`}
            >
              Issues
              {issues.length > 0 && (
                <span className="ml-1 text-[10px] text-slate-500">({issues.length})</span>
              )}
            </button>
            <button
              onClick={() => setLeftPanelTab('agents')}
              className={`flex-1 py-2 text-xs font-medium transition-colors ${
                leftPanelTab === 'agents'
                  ? 'text-indigo-400 border-b-2 border-indigo-400'
                  : 'text-slate-500 hover:text-slate-300'
              }`}
            >
              Agents
              {agentSummary.length > 0 && (
                <span className="ml-1 text-[10px] text-slate-500">({agentSummary.length})</span>
              )}
            </button>
          </div>

          {/* Content */}
          {leftPanelTab === 'issues' ? (
            <IssuesPanel />
          ) : (
            <AgentsList />
          )}
        </>
      )}
    </div>
  )
}

// Extracted agent list from AgentDispatch
function AgentsList() {
  const agentSummary = useStore((s) => s.agentSummary)

  return (
    <div className="p-3 flex-1 overflow-y-auto">
      <h2 className="text-xs font-bold text-slate-200 uppercase tracking-wider mb-3">
        Agent Dispatch
      </h2>

      <div className="space-y-2">
        {agentSummary.map((a) => {
          const pct = a.capacity > 0 ? (a.tasks / a.capacity) * 100 : 0

          return (
            <div key={a.modelType} className="group">
              <div className="flex justify-between text-[10px] mb-0.5">
                <span className={`font-medium ${a.isLocal ? 'text-emerald-400' : 'text-sky-400'}`}>
                  {a.modelType}
                </span>
                <span className="text-slate-500">
                  {a.tasks}/{a.capacity}
                </span>
              </div>

              {/* Capacity bar */}
              <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    pct > 90
                      ? 'bg-red-500'
                      : pct > 70
                      ? 'bg-yellow-500'
                      : a.isLocal
                      ? 'bg-emerald-500'
                      : 'bg-sky-500'
                  }`}
                  style={{ width: `${Math.min(100, pct)}%` }}
                />
              </div>

              <div className="flex justify-between text-[9px] text-slate-600 mt-0.5">
                <span>q{a.quality.toFixed(2)}</span>
                <span>{a.isLocal ? 'free' : `$${(a.tokenRate * 1e6).toFixed(0)}/M`}</span>
                <span>${a.cost.toFixed(1)}</span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
