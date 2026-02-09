/** Semantic Diff - Center pane showing logic summary instead of character diff
 *
 * Granularity levels:
 * - Level 1 (Intent): High-level goals met
 * - Level 2 (Architecture): Signature changes, data flow shifts
 * - Level 3 (Implementation): Raw code diff
 */

import type { IntentDelta } from '../../types'

interface SemanticDiffProps {
    delta: IntentDelta
    granularity: 1 | 2 | 3
}

export default function SemanticDiff({ delta, granularity }: SemanticDiffProps) {
    // Level 1: Intent summary
    if (granularity === 1) {
        return (
            <div className="space-y-4">
                <div className="flex items-center gap-3">
                    <span className={`text-lg ${delta.status === 'success' ? 'text-emerald-400' :
                            delta.status === 'warning' ? 'text-amber-400' : 'text-red-400'
                        }`}>
                        {delta.status === 'success' ? '✓' : delta.status === 'warning' ? '~' : '✗'}
                    </span>
                    <div>
                        <h3 className="text-lg font-semibold text-slate-200">{delta.title}</h3>
                        <p className="text-sm text-slate-400">
                            Executed by {delta.agent} ({delta.agentModel})
                        </p>
                    </div>
                </div>

                {delta.warnings.length > 0 && (
                    <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded">
                        <h4 className="text-sm font-medium text-amber-400 mb-2">Warnings</h4>
                        <ul className="text-sm text-amber-300 space-y-1">
                            {delta.warnings.map((w, i) => (
                                <li key={i}>• {w}</li>
                            ))}
                        </ul>
                    </div>
                )}

                {delta.errors.length > 0 && (
                    <div className="p-3 bg-red-500/10 border border-red-500/30 rounded">
                        <h4 className="text-sm font-medium text-red-400 mb-2">Errors</h4>
                        <ul className="text-sm text-red-300 space-y-1">
                            {delta.errors.map((e, i) => (
                                <li key={i}>• {e}</li>
                            ))}
                        </ul>
                    </div>
                )}

                <div className="text-sm text-slate-400">
                    {delta.changes.length} file(s) changed
                </div>
            </div>
        )
    }

    // Level 2: Architecture summary
    if (granularity === 2) {
        return (
            <div className="space-y-6">
                <div className="flex items-center gap-3">
                    <span className={`text-lg ${delta.status === 'success' ? 'text-emerald-400' :
                            delta.status === 'warning' ? 'text-amber-400' : 'text-red-400'
                        }`}>
                        {delta.status === 'success' ? '✓' : delta.status === 'warning' ? '~' : '✗'}
                    </span>
                    <div>
                        <h3 className="text-lg font-semibold text-slate-200">{delta.title}</h3>
                        <p className="text-sm text-slate-400">
                            {delta.agent} • {delta.agentModel}
                        </p>
                    </div>
                </div>

                {delta.changes.map((file) => (
                    <div key={file.filePath} className="border border-slate-700 rounded overflow-hidden">
                        <div className="px-3 py-2 bg-slate-800/50 border-b border-slate-700 flex items-center justify-between">
                            <span className="text-sm font-mono text-slate-300">{file.filePath}</span>
                            <span className={`text-xs px-2 py-0.5 rounded ${file.changeType === 'created' ? 'bg-emerald-500/20 text-emerald-400' :
                                    file.changeType === 'deleted' ? 'bg-red-500/20 text-red-400' :
                                        'bg-blue-500/20 text-blue-400'
                                }`}>
                                {file.changeType}
                            </span>
                        </div>

                        <div className="p-3 space-y-2">
                            <div className="text-sm text-slate-300">
                                <span className="text-indigo-400 font-medium">[Updated]</span>{' '}
                                {file.logicSummary}
                            </div>

                            {file.boilerplateSuppressed && (
                                <div className="text-xs text-slate-500">
                                    ← Boilerplate imports/generators hidden
                                </div>
                            )}
                        </div>
                    </div>
                ))}
            </div>
        )
    }

    // Level 3: Raw code diff
    return (
        <div className="space-y-4">
            <div className="flex items-center gap-3">
                <span className={`text-lg ${delta.status === 'success' ? 'text-emerald-400' :
                        delta.status === 'warning' ? 'text-amber-400' : 'text-red-400'
                    }`}>
                    {delta.status === 'success' ? '✓' : delta.status === 'warning' ? '~' : '✗'}
                </span>
                <div>
                    <h3 className="text-lg font-semibold text-slate-200">{delta.title}</h3>
                    <p className="text-sm text-slate-400">
                        {delta.agent} • {delta.agentModel}
                    </p>
                </div>
            </div>

            {delta.changes.map((file) => (
                <div key={file.filePath} className="border border-slate-700 rounded overflow-hidden">
                    <div className="px-3 py-2 bg-slate-800/50 border-b border-slate-700">
                        <span className="text-sm font-mono text-slate-300">{file.filePath}</span>
                    </div>

                    {file.rawDiff ? (
                        <pre className="p-3 text-xs font-mono overflow-auto max-h-96 bg-slate-900/50">
                            <code className="text-slate-300">{file.rawDiff}</code>
                        </pre>
                    ) : (
                        <div className="p-3 text-sm text-slate-500 italic">
                            (Raw diff not available — click to generate)
                        </div>
                    )}
                </div>
            ))}
        </div>
    )
}
