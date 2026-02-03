import { useState, useCallback, useRef, useEffect } from 'react'
import useStore from '../store'
import type { Constraints } from '../types'

interface SliderDef {
  key: keyof Constraints
  label: string
  min: number
  max: number
  step: number
  format: (v: number) => string
}

const SLIDERS: SliderDef[] = [
  {
    key: 'quality_floor',
    label: 'Quality Floor',
    min: 0,
    max: 1,
    step: 0.05,
    format: (v) => v.toFixed(2),
  },
  {
    key: 'overkill_weight',
    label: 'Overkill Weight',
    min: 0,
    max: 10,
    step: 0.5,
    format: (v) => v.toFixed(1),
  },
  {
    key: 'dep_penalty',
    label: 'Dep Penalty',
    min: 0,
    max: 500,
    step: 10,
    format: (v) => v.toFixed(0),
  },
  {
    key: 'context_bonus',
    label: 'Context Bonus',
    min: 0,
    max: 5,
    step: 0.1,
    format: (v) => v.toFixed(1),
  },
  {
    key: 'budget_cap',
    label: 'Budget Cap',
    min: 100,
    max: 10000,
    step: 100,
    format: (v) => `$${v.toFixed(0)}`,
  },
]

export default function ConstraintPanel() {
  const storeConstraints = useStore((s) => s.constraints)
  const solving = useStore((s) => s.solving)
  const solverElapsed = useStore((s) => s.solverElapsed)
  const submitSolve = useStore((s) => s.submitSolve)

  const [local, setLocal] = useState<Constraints>(storeConstraints)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Sync from store when not solving
  useEffect(() => {
    if (!solving) {
      setLocal(storeConstraints)
    }
  }, [storeConstraints, solving])

  const handleChange = useCallback(
    (key: keyof Constraints, value: number) => {
      setLocal((prev) => {
        const next = { ...prev, [key]: value }
        // Debounce submit
        if (debounceRef.current) clearTimeout(debounceRef.current)
        debounceRef.current = setTimeout(() => {
          submitSolve(next)
        }, 500)
        return next
      })
    },
    [submitSolve]
  )

  return (
    <div className="w-64 bg-slate-800/90 border-l border-slate-700 p-4 flex flex-col gap-4 overflow-y-auto">
      <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider">
        Constraints
      </h2>

      {SLIDERS.map((s) => (
        <div key={s.key}>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-slate-400">{s.label}</span>
            <span className="text-slate-200 font-mono">{s.format(local[s.key])}</span>
          </div>
          <input
            type="range"
            min={s.min}
            max={s.max}
            step={s.step}
            value={local[s.key]}
            onChange={(e) => handleChange(s.key, parseFloat(e.target.value))}
            disabled={solving}
            className="w-full h-1.5 rounded-lg appearance-none cursor-pointer
              bg-slate-600 accent-indigo-500
              disabled:opacity-50 disabled:cursor-not-allowed"
          />
        </div>
      ))}

      {/* Solving overlay */}
      {solving && (
        <div className="mt-2 p-3 rounded-lg bg-indigo-900/50 border border-indigo-500/30">
          <div className="text-xs text-indigo-300 flex items-center gap-2">
            <div className="w-3 h-3 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
            Solving... {solverElapsed.toFixed(1)}s
          </div>
          <div className="mt-2 h-1 bg-slate-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-indigo-500 transition-all duration-1000"
              style={{ width: `${Math.min(100, (solverElapsed / 30) * 100)}%` }}
            />
          </div>
        </div>
      )}
    </div>
  )
}
