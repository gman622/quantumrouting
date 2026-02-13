import { useState } from 'react'
import useStore from '../store'
import type { StaffPlanResponse } from '../types'

const AGENT_COLORS: Record<string, string> = {
  'feature-trailblazer': 'text-green-400',
  'tenacious-unit-tester': 'text-blue-400',
  'docs-logs-wizard': 'text-purple-300',
  'code-ace-reviewer': 'text-red-400',
  'bug-hunter': 'text-yellow-400',
  'testing-guru': 'text-cyan-400',
  'task-predator': 'text-orange-400',
}

function InputView() {
  const githubRepo = useStore((s) => s.githubRepo)
  const planLoading = useStore((s) => s.planLoading)
  const planError = useStore((s) => s.planError)
  const generatePlan = useStore((s) => s.generatePlan)

  const [issueNumber, setIssueNumber] = useState('')
  const [repoOverride, setRepoOverride] = useState('')

  const effectiveRepo = repoOverride || githubRepo || ''

  const handlePlan = () => {
    const num = parseInt(issueNumber, 10)
    if (isNaN(num) || num <= 0) return
    generatePlan(num, effectiveRepo || undefined)
  }

  return (
    <>
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

      {/* Plan It button */}
      <button
        onClick={handlePlan}
        disabled={planLoading || !issueNumber}
        className={`w-full py-2 rounded text-xs font-medium transition-colors ${
          planLoading
            ? 'bg-indigo-800 text-indigo-300 cursor-wait'
            : !issueNumber
            ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
            : 'bg-indigo-600 hover:bg-indigo-500 text-white cursor-pointer'
        }`}
      >
        {planLoading ? (
          <span className="flex items-center justify-center gap-2">
            <div className="w-2 h-2 bg-indigo-400 rounded-full animate-pulse" />
            Planning...
          </span>
        ) : (
          'Plan It'
        )}
      </button>

      {/* Error */}
      {planError && (
        <div className="mt-3 p-2 bg-red-900/30 border border-red-800 rounded text-xs text-red-300">
          {planError}
        </div>
      )}
    </>
  )
}

function PlanReviewView({ plan }: { plan: StaffPlanResponse }) {
  const materializing = useStore((s) => s.materializing)
  const materializeError = useStore((s) => s.materializeError)
  const materializeIssue = useStore((s) => s.materializeIssue)
  const clearPlan = useStore((s) => s.clearPlan)
  const githubRepo = useStore((s) => s.githubRepo)

  const [expandedWaves, setExpandedWaves] = useState<Set<number>>(new Set([0]))

  const toggleWave = (idx: number) => {
    setExpandedWaves((prev) => {
      const next = new Set(prev)
      if (next.has(idx)) next.delete(idx)
      else next.add(idx)
      return next
    })
  }

  const handleMaterialize = () => {
    materializeIssue(plan.parent_issue, githubRepo || undefined)
  }

  const sp = plan.staffing_plan

  return (
    <>
      {/* Parent issue header */}
      <div className="p-2 bg-slate-900/50 border border-slate-700 rounded mb-3">
        <div className="text-[10px] text-slate-500 mb-1">Parent Issue</div>
        <div className="text-xs text-slate-200">
          #{plan.parent_issue} {plan.parent_title}
        </div>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 gap-2 mb-3">
        <div className="p-2 bg-slate-900/50 border border-slate-700 rounded">
          <div className="text-[10px] text-slate-500">Intents</div>
          <div className="text-sm font-mono text-slate-200">{sp.total_intents}</div>
        </div>
        <div className="p-2 bg-slate-900/50 border border-slate-700 rounded">
          <div className="text-[10px] text-slate-500">Waves</div>
          <div className="text-sm font-mono text-slate-200">{sp.total_waves}</div>
        </div>
        <div className="p-2 bg-slate-900/50 border border-slate-700 rounded">
          <div className="text-[10px] text-slate-500">Parallelism</div>
          <div className="text-sm font-mono text-slate-200">{sp.peak_parallelism}</div>
        </div>
        <div className="p-2 bg-slate-900/50 border border-slate-700 rounded">
          <div className="text-[10px] text-slate-500">Est. Cost</div>
          <div className="text-sm font-mono text-slate-200">
            ${sp.total_estimated_cost.toFixed(4)}
          </div>
        </div>
      </div>

      {/* Wave breakdown */}
      <div className="mb-3">
        <div className="text-[10px] text-slate-500 mb-1">Wave Breakdown</div>
        <div className="space-y-1">
          {(sp.waves || []).map((wave) => {
            const waveCost = wave.intents.reduce((s, i) => s + i.estimated_cost, 0)
            const isExpanded = expandedWaves.has(wave.wave)
            return (
              <div key={wave.wave} className="bg-slate-900/50 border border-slate-700 rounded">
                <button
                  onClick={() => toggleWave(wave.wave)}
                  className="w-full flex items-center justify-between p-1.5 text-xs text-slate-300 hover:text-slate-100"
                >
                  <span>
                    <span className="text-slate-500 mr-1">{isExpanded ? '\u25BE' : '\u25B8'}</span>
                    Wave {wave.wave}{' '}
                    <span className="text-slate-500">
                      ({wave.agents_needed} agent{wave.agents_needed !== 1 ? 's' : ''}, ${waveCost.toFixed(4)})
                    </span>
                  </span>
                </button>
                {isExpanded && (
                  <div className="px-2 pb-2 space-y-0.5">
                    {wave.intents.map((intent) => (
                      <div key={intent.id} className="flex items-center gap-1 text-[10px] font-mono">
                        <span className="text-slate-400 truncate flex-1">{intent.id}</span>
                        <span className="text-slate-600">-&gt;</span>
                        <span className={`${AGENT_COLORS[intent.profile] || 'text-slate-400'} truncate`}>
                          {intent.profile}
                        </span>
                        <span className="text-slate-600">({intent.model})</span>
                        <span className="text-slate-600">[{intent.complexity}]</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Profile load */}
      {Object.keys(sp.profile_load).length > 0 && (
        <div className="mb-3">
          <div className="text-[10px] text-slate-500 mb-1">Profile Load</div>
          <div className="space-y-1">
            {Object.entries(sp.profile_load).map(([profile, count]) => (
              <div key={profile} className="flex items-center gap-2">
                <span className={`text-[10px] w-32 truncate ${AGENT_COLORS[profile] || 'text-slate-400'}`}>
                  {profile}
                </span>
                <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-indigo-500 rounded-full"
                    style={{
                      width: `${Math.min(100, (count / sp.total_intents) * 100)}%`,
                    }}
                  />
                </div>
                <span className="text-[10px] text-slate-500 w-4 text-right">{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Action buttons */}
      <div className="flex gap-2">
        <button
          onClick={clearPlan}
          className="flex-1 py-2 rounded text-xs font-medium bg-slate-700 hover:bg-slate-600 text-slate-300 transition-colors"
        >
          Back
        </button>
        <button
          onClick={handleMaterialize}
          disabled={materializing}
          className={`flex-1 py-2 rounded text-xs font-medium transition-colors ${
            materializing
              ? 'bg-green-900 text-green-300 cursor-wait'
              : 'bg-green-600 hover:bg-green-500 text-white cursor-pointer'
          }`}
        >
          {materializing ? (
            <span className="flex items-center justify-center gap-2">
              <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
              Creating...
            </span>
          ) : (
            'Materialize'
          )}
        </button>
      </div>

      {/* Error */}
      {materializeError && (
        <div className="mt-3 p-2 bg-red-900/30 border border-red-800 rounded text-xs text-red-300">
          {materializeError}
        </div>
      )}
    </>
  )
}

function MaterializedView() {
  const materializeResult = useStore((s) => s.materializeResult)!
  const clearPlan = useStore((s) => s.clearPlan)
  const githubRepo = useStore((s) => s.githubRepo)

  const effectiveRepo = githubRepo || ''

  return (
    <>
      {/* Summary */}
      <div className="p-2 bg-slate-900/50 border border-slate-700 rounded mb-3">
        <div className="text-[10px] text-slate-500 mb-1">Parent Issue</div>
        <div className="text-xs text-slate-200">
          #{materializeResult.parent_issue} {materializeResult.parent_title}
        </div>
      </div>

      {/* Staffing plan stats */}
      <div className="grid grid-cols-2 gap-2 mb-3">
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
      <div className="mb-3">
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
        <div className="mb-3">
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

      {/* Staff Another button */}
      <button
        onClick={clearPlan}
        className="w-full py-2 rounded text-xs font-medium bg-slate-700 hover:bg-slate-600 text-slate-300 transition-colors"
      >
        Staff Another
      </button>
    </>
  )
}

export default function StaffingPanel() {
  const staffingPlan = useStore((s) => s.staffingPlan)
  const materializeResult = useStore((s) => s.materializeResult)

  return (
    <div className="p-3 flex-1 overflow-y-auto">
      <h2 className="text-xs font-bold text-slate-200 uppercase tracking-wider mb-3">
        Staffing Engine
      </h2>

      {materializeResult ? (
        <MaterializedView />
      ) : staffingPlan ? (
        <PlanReviewView plan={staffingPlan} />
      ) : (
        <InputView />
      )}
    </div>
  )
}
