import { memo } from 'react'
import { Handle, Position, type NodeProps } from 'reactflow'
import type { StageNodeData } from '../../types'

const STATUS_BG = {
  satisfied: 'border-green-500/60 bg-green-500/10',
  overkill: 'border-yellow-500/60 bg-yellow-500/10',
  violated: 'border-red-500/60 bg-red-500/10',
} as const

function StageNode({ data }: NodeProps<StageNodeData>) {
  const { satisfied, overkill, violated } = data.counts
  const total = satisfied + overkill + violated

  return (
    <div
      className={`rounded-xl border-2 px-6 py-4 min-w-[180px] shadow-lg transition-all duration-500 ${STATUS_BG[data.status]}`}
    >
      <Handle type="target" position={Position.Left} className="!bg-slate-500" />

      <div className="text-sm font-bold text-slate-200 mb-2">{data.label}</div>

      <div className="text-xs text-slate-400 space-y-1">
        <div className="flex justify-between">
          <span>Tasks</span>
          <span className="text-slate-200">{data.taskCount.toLocaleString()}</span>
        </div>
        <div className="flex justify-between">
          <span>Cost</span>
          <span className="text-slate-200">${data.cost.toFixed(2)}</span>
        </div>
      </div>

      {/* Mini status bar */}
      <div className="mt-3 flex h-2 rounded-full overflow-hidden bg-slate-700/50">
        {total > 0 && (
          <>
            <div
              className="bg-green-500 transition-all duration-500"
              style={{ width: `${(satisfied / total) * 100}%` }}
            />
            <div
              className="bg-yellow-500 transition-all duration-500"
              style={{ width: `${(overkill / total) * 100}%` }}
            />
            <div
              className="bg-red-500 transition-all duration-500"
              style={{ width: `${(violated / total) * 100}%` }}
            />
          </>
        )}
      </div>
      <div className="mt-1 flex justify-between text-[10px] text-slate-500">
        <span>{satisfied}</span>
        <span>{overkill}</span>
        <span>{violated}</span>
      </div>

      <Handle type="source" position={Position.Right} className="!bg-slate-500" />
    </div>
  )
}

export default memo(StageNode)
