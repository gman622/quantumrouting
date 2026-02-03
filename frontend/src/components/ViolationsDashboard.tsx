import useStore from '../store'

const STATUS_CONFIG = [
  { key: 'satisfied', label: 'Satisfied', color: 'bg-green-500', text: 'text-green-400' },
  { key: 'overkill', label: 'Overkill', color: 'bg-yellow-500', text: 'text-yellow-400' },
  { key: 'violated', label: 'Violated', color: 'bg-red-500', text: 'text-red-400' },
] as const

export default function ViolationsDashboard() {
  const meta = useStore((s) => s.meta)

  if (!meta) return null

  const total = meta.totalTasks
  const counts = meta.statusCounts

  return (
    <div className="bg-slate-800/90 border-t border-slate-700 px-6 py-3">
      <div className="flex items-center gap-8">
        {/* Status counts */}
        <div className="flex gap-6">
          {STATUS_CONFIG.map((s) => (
            <div key={s.key} className="flex items-center gap-2">
              <div className={`w-2.5 h-2.5 rounded-full ${s.color}`} />
              <span className="text-xs text-slate-400">{s.label}</span>
              <span className={`text-sm font-bold ${s.text} font-mono`}>
                {counts[s.key].toLocaleString()}
              </span>
            </div>
          ))}
        </div>

        {/* Divider */}
        <div className="w-px h-6 bg-slate-600" />

        {/* Summary stats */}
        <div className="flex gap-6 text-xs">
          <div>
            <span className="text-slate-500">Assigned </span>
            <span className="text-slate-200 font-mono">
              {meta.assignedTasks.toLocaleString()}/{total.toLocaleString()}
            </span>
          </div>
          <div>
            <span className="text-slate-500">Cost </span>
            <span className="text-slate-200 font-mono">${meta.totalCost.toFixed(2)}</span>
          </div>
          <div>
            <span className="text-slate-500">Dep Violations </span>
            <span className={`font-mono ${meta.depViolations > 0 ? 'text-red-400' : 'text-slate-200'}`}>
              {meta.depViolations}
            </span>
          </div>
        </div>

        {/* Full-width status bar */}
        <div className="flex-1 h-2 rounded-full overflow-hidden bg-slate-700/50 flex">
          {total > 0 && (
            <>
              <div
                className="bg-green-500 transition-all duration-700"
                style={{ width: `${(counts.satisfied / total) * 100}%` }}
              />
              <div
                className="bg-yellow-500 transition-all duration-700"
                style={{ width: `${(counts.overkill / total) * 100}%` }}
              />
              <div
                className="bg-red-500 transition-all duration-700"
                style={{ width: `${(counts.violated / total) * 100}%` }}
              />
            </>
          )}
        </div>
      </div>
    </div>
  )
}
