import useStore from '../store'

export default function AgentDispatch() {
  const agentSummary = useStore((s) => s.agentSummary)
  const agentPanelOpen = useStore((s) => s.agentPanelOpen)
  const setAgentPanelOpen = useStore((s) => s.setAgentPanelOpen)

  return (
    <div
      className={`bg-slate-800/90 border-r border-slate-700 transition-all duration-300 overflow-hidden flex flex-col ${
        agentPanelOpen ? 'w-56' : 'w-8'
      }`}
    >
      {/* Toggle button */}
      <button
        onClick={() => setAgentPanelOpen(!agentPanelOpen)}
        className="w-full py-2 text-slate-500 hover:text-slate-300 text-xs border-b border-slate-700"
      >
        {agentPanelOpen ? '<' : '>'}
      </button>

      {agentPanelOpen && (
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
      )}
    </div>
  )
}
