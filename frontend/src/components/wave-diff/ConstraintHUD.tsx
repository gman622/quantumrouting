/** Constraint HUD - Right pane showing before/after metrics comparison
 *
 * Displays:
 * - P99 Latency, Test Coverage, Token Cost, Chain Coherence, etc.
 * - Before → After with color-coded change indicators
 */

import type { MetricSnapshot, MetricDelta } from '../../types'

interface ConstraintHUDProps {
    before: MetricSnapshot
    after: MetricSnapshot
    deltas: MetricDelta[]
}

export default function ConstraintHUD({ before, after, deltas }: ConstraintHUDProps) {
    const hasRegression = deltas.some((d) => d.changeType === 'regression')
    const hasImprovement = deltas.some((d) => d.changeType === 'improvement')

    return (
        <div className="flex-1 overflow-auto">
            <div className="p-3 bg-slate-800 border-b border-slate-700">
                <h2 className="text-sm font-semibold text-slate-200">Constraint Impact</h2>
                <p className="text-xs text-slate-400 mt-0.5">
                    Before → After
                </p>
            </div>

            {/* Status bar */}
            <div className={`p-3 border-b border-slate-700 ${hasRegression ? 'bg-red-500/10' : hasImprovement ? 'bg-emerald-500/10' : 'bg-slate-800/30'
                }`}>
                <div className="flex items-center gap-2">
                    {hasRegression ? (
                        <span className="text-red-400">⚠ Some constraints regressed</span>
                    ) : hasImprovement ? (
                        <span className="text-emerald-400">✓ All constraints stable or improved</span>
                    ) : (
                        <span className="text-slate-400">~ No significant changes</span>
                    )}
                </div>
            </div>

            {/* Metrics table */}
            <table className="w-full text-sm">
                <thead className="bg-slate-800/30">
                    <tr>
                        <th className="text-left p-2 text-xs font-medium text-slate-400">Metric</th>
                        <th className="text-right p-2 text-xs font-medium text-slate-400">Before</th>
                        <th className="text-right p-2 text-xs font-medium text-slate-400">After</th>
                        <th className="text-right p-2 text-xs font-medium text-slate-400">Δ</th>
                    </tr>
                </thead>
                <tbody>
                    {deltas.map((delta) => (
                        <tr
                            key={delta.name}
                            className={`border-b border-slate-700/50 ${delta.changeType === 'regression' ? 'bg-red-500/5' :
                                    delta.changeType === 'improvement' ? 'bg-emerald-500/5' : ''
                                }`}
                        >
                            <td className="p-2">
                                <span className="text-slate-300">{delta.name}</span>
                            </td>
                            <td className="p-2 text-right text-slate-400">
                                {formatMetric(delta.name, delta.before)}
                            </td>
                            <td className="p-2 text-right text-slate-300 font-medium">
                                {formatMetric(delta.name, delta.after)}
                            </td>
                            <td className="p-2 text-right">
                                <span className={`text-xs font-medium ${delta.changeType === 'regression' ? 'text-red-400' :
                                        delta.changeType === 'improvement' ? 'text-emerald-400' : 'text-slate-500'
                                    }`}>
                                    {delta.change > 0 ? '+' : ''}{formatMetric(delta.name, delta.change)}
                                </span>
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>

            {/* Cumulative cost note */}
            <div className="p-3 bg-slate-800/30 border-t border-slate-700">
                <div className="text-xs text-slate-400">
                    Cumulative token cost for this wave:
                </div>
                <div className="text-lg font-semibold text-slate-200">
                    ${after.tokenCost.toFixed(2)}
                    {after.tokenCost > before.tokenCost && (
                        <span className="text-red-400 text-sm ml-2">
                            (+${(after.tokenCost - before.tokenCost).toFixed(2)})
                        </span>
                    )}
                </div>
            </div>
        </div>
    )
}

function formatMetric(name: string, value: number): string {
    if (name.includes('Latency') || name.includes('latency')) {
        return `${value.toFixed(0)}ms`
    }
    if (name.includes('Coverage') || name.includes('coverage') || name.includes('Coherence')) {
        return `${(value * 100).toFixed(1)}%`
    }
    if (name.includes('Cost') || name.includes('cost')) {
        return `$${value.toFixed(2)}`
    }
    if (name.includes('Gate') || name.includes('gate')) {
        return `${(value * 100).toFixed(0)}%`
    }
    if (name.includes('Dependency') || name.includes('dependency')) {
        return value.toString()
    }
    return value.toFixed(2)
}
