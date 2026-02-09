/** Impact Heatmap - Ghost map showing predicted telemetry changes
 *
 * Red zones: High-risk logic changes
 * Blue zones: Stable, additive changes (docs, tests)
 *
 * Displays as an overlay on the code area showing "risk zones"
 */

import type { ImpactPrediction } from '../../types'

interface ImpactHeatmapProps {
    files: string[]
    predictions: ImpactPrediction[]
}

const RISK_COLORS = {
    high: 'bg-red-500/30 border-red-500/50 text-red-300',
    medium: 'bg-amber-500/20 border-amber-500/40 text-amber-300',
    low: 'bg-blue-500/20 border-blue-500/40 text-blue-300',
}

const RISK_BADGES = {
    high: '🔴 High Risk',
    medium: '🟡 Medium Risk',
    low: '🔵 Low Risk',
}

export default function ImpactHeatmap({ files, predictions }: ImpactHeatmapProps) {
    if (predictions.length === 0) return null

    // Create a mapping of file -> prediction
    const predictionMap = new Map(predictions.map((p) => [p.filePath, p]))

    return (
        <div className="absolute bottom-0 left-0 right-0 bg-slate-900/95 border-t border-slate-700 p-3">
            <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-medium text-slate-400">Impact Heatmap</span>
                <div className="flex gap-3 text-xs">
                    <span className={RISK_COLORS.high + ' px-2 py-0.5 rounded border'}>
                        🔴 High Risk
                    </span>
                    <span className={RISK_COLORS.medium + ' px-2 py-0.5 rounded border'}>
                        🟡 Medium Risk
                    </span>
                    <span className={RISK_COLORS.low + ' px-2 py-0.5 rounded border'}>
                        🔵 Low Risk
                    </span>
                </div>
            </div>

            {/* File tiles */}
            <div className="flex flex-wrap gap-2">
                {files.map((file) => {
                    const prediction = predictionMap.get(file)
                    const risk = prediction?.riskLevel || 'low'
                    const colorClass = RISK_COLORS[risk]
                    const badge = RISK_BADGES[risk]

                    return (
                        <div
                            key={file}
                            className={`px-3 py-1.5 rounded border text-xs font-mono ${colorClass}`}
                        >
                            <div className="flex items-center gap-2">
                                <span>{file.split('/').pop()}</span>
                                <span className="opacity-60">{badge}</span>
                            </div>
                            {prediction && prediction.affectedMetrics.length > 0 && (
                                <div className="mt-1 text-xs opacity-70">
                                    ← {prediction.affectedMetrics.join(', ')}
                                </div>
                            )}
                        </div>
                    )
                })}
            </div>
        </div>
    )
}
