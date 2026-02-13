import { useState } from 'react'
import useStore from '../store'

const AGENT_COLORS: Record<string, string> = {
  'feature-trailblazer': 'text-green-400',
  'tenacious-unit-tester': 'text-blue-400',
  'docs-logs-wizard': 'text-purple-300',
  'code-ace-reviewer': 'text-red-400',
}

export default function StaffingPanel() {
  const githubRepo = useStore((s) => s.githubRepo)
  const materializing = useStore((s) => s.materializing)
  const materializeResult = useStore((s) => s.materializeResult)
  const materializeError = useStore((s) => s.materializeError)
  const materializeIssue = useStore((s) => s.materializeIssue)

  const [issueNumber, setIssueNumber] = useState('')
  const [repoOverride, setRepoOverride] = useState('')

  const effectiveRepo = repoOverride || githubRepo || ''

  const handleMaterialize = () => {
    const num = parseInt(issueNumber, 10)
    if (isNaN(num) || num <= 0) return
    materializeIssue(num, effectiveRepo || undefined)
  }

  return (
    <div className="p-3 flex-1 overflow-y-auto">
      <h2 className="text-xs font-bold text-slate-200 uppercase tracking-wider mb-3">
        Staffing Engine
      </h2>

      {/* Repo input */}
      <div className="mb-3">
        <label className="block text-[10px] text-slate-500 mb-1">Repository</label>
        <input
          type="text"
          value={repoOverride}
          onChange={(e) => setRepoOverride(e.target.value)}
          placeholder={githubRepo || 'owner/repo (current)'}
          className="w-full px-2 py-1.5 bg-slate-900 border border-slate-600 rounded text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
        />
      </div>

      {/* Issue number input */}
      <div className="mb-3">
        <label className="block text-[10px] text-slate-500 mb-1">Issue Number</label>
        <input
          type="number"
          value={issueNumber}
          onChange={(e) => setIssueNumber(e.target.value)}
          placeholder="#13"
          min="1"
          className="w-full px-2 py-1.5 bg-slate-900 border border-slate-600 rounded text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
        />
      </div>

      {/* Staff It button */}
      <button
        onClick={handleMaterialize}
        disabled={materializing || !issueNumber}
        className={`w-full py-2 rounded text-xs font-medium transition-colors ${
          materializing
            ? 'bg-indigo-800 text-indigo-300 cursor-wait'
            : !issueNumber
            ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
            : 'bg-indigo-600 hover:bg-indigo-500 text-white cursor-pointer'
        }`}
      >
        {materializing ? (
          <span className="flex items-center justify-center gap-2">
            <div className="w-2 h-2 bg-indigo-400 rounded-full animate-pulse" />
            Staffing...
          </span>
        ) : (
          'Staff It'
        )}
      </button>

      {/* Error */}
      {materializeError && (
        <div className="mt-3 p-2 bg-red-900/30 border border-red-800 rounded text-xs text-red-300">
          {materializeError}
        </div>
      )}

      {/* Results */}
      {materializeResult && (
        <div className="mt-3 space-y-3">
          {/* Summary */}
          <div className="p-2 bg-slate-900/50 border border-slate-700 rounded">
            <div className="text-[10px] text-slate-500 mb-1">Parent Issue</div>
            <div className="text-xs text-slate-200">
              #{materializeResult.parent_issue} {materializeResult.parent_title}
            </div>
          </div>

          {/* Staffing plan stats */}
          <div className="grid grid-cols-2 gap-2">
            <div className="p-2 bg-slate-900/50 border border-slate-700 rounded">
              <div className="text-[10px] text-slate-500">Intents</div>
              <div className="text-sm font-mono text-slate-200">
                {materializeResult.staffing_plan.total_intents}
              </div>
            </div>
            <div className="p-2 bg-slate-900/50 border border-slate-700 rounded">
              <div className="text-[10px] text-slate-500">Waves</div>
              <div className="text-sm font-mono text-slate-200">
                {materializeResult.staffing_plan.total_waves}
              </div>
            </div>
            <div className="p-2 bg-slate-900/50 border border-slate-700 rounded">
              <div className="text-[10px] text-slate-500">Parallelism</div>
              <div className="text-sm font-mono text-slate-200">
                {materializeResult.staffing_plan.peak_parallelism}
              </div>
            </div>
            <div className="p-2 bg-slate-900/50 border border-slate-700 rounded">
              <div className="text-[10px] text-slate-500">Est. Cost</div>
              <div className="text-sm font-mono text-slate-200">
                ${materializeResult.staffing_plan.total_estimated_cost.toFixed(4)}
              </div>
            </div>
          </div>

          {/* Companion issues */}
          <div>
            <div className="text-[10px] text-slate-500 mb-1">Companion Issues</div>
            <div className="space-y-1">
              {Object.entries(materializeResult.companion_issues).map(([agent, num]) => (
                <div
                  key={agent}
                  className="flex items-center justify-between p-1.5 bg-slate-900/50 border border-slate-700 rounded"
                >
                  <span className={`text-xs font-medium ${AGENT_COLORS[agent] || 'text-slate-300'}`}>
                    {agent}
                  </span>
                  <a
                    href={
                      effectiveRepo
                        ? `https://github.com/${effectiveRepo}/issues/${num}`
                        : `#${num}`
                    }
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-indigo-400 hover:text-indigo-300"
                  >
                    #{num}
                  </a>
                </div>
              ))}
            </div>
          </div>

          {/* Profile load */}
          {Object.keys(materializeResult.staffing_plan.profile_load).length > 0 && (
            <div>
              <div className="text-[10px] text-slate-500 mb-1">Profile Load</div>
              <div className="space-y-1">
                {Object.entries(materializeResult.staffing_plan.profile_load).map(
                  ([profile, count]) => (
                    <div key={profile} className="flex items-center gap-2">
                      <span className={`text-[10px] w-32 truncate ${AGENT_COLORS[profile] || 'text-slate-400'}`}>
                        {profile}
                      </span>
                      <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-indigo-500 rounded-full"
                          style={{
                            width: `${Math.min(100, (count / materializeResult.staffing_plan.total_intents) * 100)}%`,
                          }}
                        />
                      </div>
                      <span className="text-[10px] text-slate-500 w-4 text-right">{count}</span>
                    </div>
                  ),
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
