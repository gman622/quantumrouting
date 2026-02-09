/** Intent Sidebar - Left pane of WaveDiff showing DAG nodes touched by this wave
 *
 * Displays:
 * - Green: Successfully fulfilled intents
 * - Yellow: Fulfilled but "constraint-tense" (barely passed gate)
 * - Red: Failed to satisfy constraints
 */

import type { IntentDelta } from '../../types'

interface IntentSidebarProps {
    intents: IntentDelta[]
    selectedId: string | null
    onSelect: (id: string) => void
}

const STATUS_COLORS = {
    success: 'bg-emerald-500/20 border-emerald-500/50 text-emerald-400',
    warning: 'bg-amber-500/20 border-amber-500/50 text-amber-400',
    failed: 'bg-red-500/20 border-red-500/50 text-red-400',
}

const STATUS_ICONS = {
    success: '✓',
    warning: '~',
    failed: '✗',
}

export default function IntentSidebar({
    intents,
    selectedId,
    onSelect,
}: IntentSidebarProps) {
    const successCount = intents.filter((i) => i.status === 'success').length
    const warningCount = intents.filter((i) => i.status === 'warning').length
    const failedCount = intents.filter((i) => i.status === 'failed').length

    return (
        <div className="flex-1 overflow-auto">
            {/* Summary header */}
            <div className="p-3 bg-slate-800/50 border-b border-slate-700">
                <div className="flex gap-3 text-xs">
                    <span className="text-emerald-400">{successCount} fulfilled</span>
                    <span className="text-amber-400">{warningCount} tense</span>
                    <span className="text-red-400">{failedCount} failed</span>
                </div>
            </div>

            {/* Intent list */}
            <div className="p-2 space-y-1">
                {intents.map((intent) => {
                    const isSelected = intent.intentId === selectedId
                    const colorClass = STATUS_COLORS[intent.status]

                    return (
                        <button
                            key={intent.intentId}
                            onClick={() => onSelect(intent.intentId)}
                            className={`w-full text-left p-2 rounded border text-sm transition-all ${isSelected
                                    ? 'bg-slate-700/50 border-slate-600'
                                    : 'bg-transparent border-transparent hover:bg-slate-800'
                                } ${colorClass}`}
                        >
                            <div className="flex items-start gap-2">
                                <span className="text-xs mt-0.5">
                                    {STATUS_ICONS[intent.status]}
                                </span>
                                <div className="flex-1 min-w-0">
                                    <div className="font-medium truncate">{intent.title}</div>
                                    <div className="text-xs opacity-60 mt-0.5">
                                        {intent.agentModel} • {intent.agent}
                                    </div>
                                    {intent.warnings.length > 0 && (
                                        <div className="text-xs text-amber-400 mt-1">
                                            ⚠ {intent.warnings.length} warning(s)
                                        </div>
                                    )}
                                    {intent.errors.length > 0 && (
                                        <div className="text-xs text-red-400 mt-1">
                                            ⚠ {intent.errors.length} error(s)
                                        </div>
                                    )}
                                </div>
                            </div>
                        </button>
                    )
                })}
            </div>
        </div>
    )
}
