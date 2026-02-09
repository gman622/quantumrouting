/** WaveDiff Panel - Mass Diff view for Conductor-era code review
 *
 * 3-pane interface:
 * - Left: Intent Sidebar (Why) - DAG nodes touched by this wave
 * - Center: Semantic Diff (What) - Logic summary, not character diff
 * - Right: Constraint HUD (Impact) - Before/after metrics comparison
 *
 * Includes Granularity Slider and Impact Heatmap visualization.
 */

import { useState } from 'react'
import type { WaveData, IntentDelta, MetricDelta, ConstraintHUDData } from '../types'
import IntentSidebar from './wave-diff/IntentSidebar'
import SemanticDiff from './wave-diff/SemanticDiff'
import ConstraintHUD from './wave-diff/ConstraintHUD'
import GranularitySlider from './wave-diff/GranularitySlider'
import ImpactHeatmap from './wave-diff/ImpactHeatmap'

interface WaveDiffPanelProps {
    waveId: string
    waveData: WaveData
    isOpen: boolean
    onClose: () => void
    onRejectIntent: (intentId: string, reason: string) => void
    onRevertWave: (waveId: string) => void
}

export default function WaveDiffPanel({
    waveId,
    waveData,
    isOpen,
    onClose,
    onRejectIntent,
    onRevertWave,
}: WaveDiffPanelProps) {
    const [granularity, setGranularity] = useState<1 | 2 | 3>(2)
    const [selectedIntent, setSelectedIntent] = useState<string | null>(null)
    const [showHeatmap, setShowHeatmap] = useState(true)

    if (!isOpen) return null

    const selectedIntentDelta = waveData.intentDeltas.find(
        (delta) => delta.intentId === selectedIntent
    )

    return (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex">
            {/* Main 3-pane diff area */}
            <div className="flex-1 flex m-4 rounded-lg overflow-hidden bg-slate-900 border border-slate-700">

                {/* Left: Intent Sidebar (The "Why") */}
                <div className="w-64 border-r border-slate-700 flex flex-col">
                    <div className="p-3 bg-slate-800 border-b border-slate-700">
                        <h2 className="text-sm font-semibold text-slate-200">
                            Intent Wave #{waveId}
                        </h2>
                        <p className="text-xs text-slate-400 mt-1">
                            {waveData.intentDeltas.length} intents • {waveData.filesChanged} files
                        </p>
                    </div>

                    <IntentSidebar
                        intents={waveData.intentDeltas}
                        selectedId={selectedIntent}
                        onSelect={setSelectedIntent}
                    />
                </div>

                {/* Center: Semantic Diff (The "What") */}
                <div className="flex-1 flex flex-col min-w-0">
                    <div className="p-3 bg-slate-800/50 border-b border-slate-700 flex items-center justify-between">
                        <div>
                            <h2 className="text-sm font-semibold text-slate-200">Semantic Changes</h2>
                            <p className="text-xs text-slate-400">
                                {granularity === 1 && 'Level 1: Intent Summary'}
                                {granularity === 2 && 'Level 2: Architecture & Logic'}
                                {granularity === 3 && 'Level 3: Raw Code Diff'}
                            </p>
                        </div>
                        <GranularitySlider value={granularity} onChange={setGranularity} />
                    </div>

                    <div className="flex-1 overflow-auto p-4">
                        {selectedIntentDelta ? (
                            <SemanticDiff
                                delta={selectedIntentDelta}
                                granularity={granularity}
                            />
                        ) : (
                            <div className="h-full flex items-center justify-center text-slate-500 text-sm">
                                Select an intent to view changes
                            </div>
                        )}
                    </div>

                    {/* Impact Heatmap overlay */}
                    {showHeatmap && (
                        <ImpactHeatmap
                            files={waveData.files}
                            predictions={waveData.impactPredictions}
                        />
                    )}
                </div>

                {/* Right: Constraint HUD (The "Impact") */}
                <div className="w-80 border-l border-slate-700 flex flex-col">
                    <ConstraintHUD
                        before={waveData.metricsBefore}
                        after={waveData.metricsAfter}
                        deltas={waveData.metricDeltas}
                    />

                    {/* Reject/Revert actions */}
                    <div className="p-4 border-t border-slate-700 bg-slate-800/30">
                        <button
                            onClick={() => onRejectIntent(selectedIntent || '', 'Change implementation')}
                            disabled={!selectedIntent}
                            className="w-full mb-2 px-3 py-2 bg-amber-600/20 hover:bg-amber-600/30 
                       disabled:opacity-30 disabled:cursor-not-allowed
                       text-amber-400 text-sm rounded transition-colors"
                        >
                            Reject Intent
                        </button>
                        <button
                            onClick={() => onRevertWave(waveId)}
                            className="w-full px-3 py-2 bg-red-600/20 hover:bg-red-600/30 
                       text-red-400 text-sm rounded transition-colors"
                        >
                            Revert Entire Wave
                        </button>
                    </div>
                </div>
            </div>

            {/* Toggle heatmap */}
            <button
                onClick={() => setShowHeatmap(!showHeatmap)}
                className={`absolute top-6 right-6 px-3 py-1 rounded text-xs font-medium transition-colors ${showHeatmap
                        ? 'bg-indigo-600 text-white'
                        : 'bg-slate-700 text-slate-300'
                    }`}
            >
                {showHeatmap ? 'Hide' : 'Show'} Impact Map
            </button>

            {/* Close button */}
            <button
                onClick={onClose}
                className="absolute top-6 right-32 px-3 py-1 bg-slate-700 hover:bg-slate-600 
                 text-slate-300 text-xs rounded transition-colors"
            >
                Close
            </button>
        </div>
    )
}
