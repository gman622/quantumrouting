/** Granularity Slider - Controls abstraction level of the diff view
 *
 * Level 1 (Intent): Shows only which high-level goals were met
 * Level 2 (Architecture): Shows signature changes and data flow shifts
 * Level 3 (Implementation): Shows the raw code diff
 */

interface GranularitySliderProps {
    value: 1 | 2 | 3
    onChange: (value: 1 | 2 | 3) => void
}

const LABELS = [
    { level: 1, label: 'Intent', desc: 'High-level goals' },
    { level: 2, label: 'Architecture', desc: 'Data flow & signatures' },
    { level: 3, label: 'Code', desc: 'Raw diff' },
]

export default function GranularitySlider({ value, onChange }: GranularitySliderProps) {
    return (
        <div className="flex flex-col gap-1">
            <div className="flex gap-1 bg-slate-700/50 rounded p-0.5">
                {LABELS.map((item) => (
                    <button
                        key={item.level}
                        onClick={() => onChange(item.level as 1 | 2 | 3)}
                        className={`px-3 py-1 text-xs rounded transition-all ${value === item.level
                                ? 'bg-indigo-600 text-white'
                                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-600/50'
                            }`}
                    >
                        {item.label}
                    </button>
                ))}
            </div>
            <span className="text-xs text-slate-500 text-right">
                {LABELS[value - 1].desc}
            </span>
        </div>
    )
}
