import { memo } from 'react'
import { Handle, Position, type NodeProps } from 'reactflow'
import type { ClusterNodeData } from '../../types'

const STATUS_RING = {
  satisfied: 'ring-green-500/50',
  overkill: 'ring-yellow-500/50',
  violated: 'ring-red-500/50',
} as const

const SIZE_SCALE = [
  [10, 'w-16 h-16'],
  [50, 'w-20 h-20'],
  [200, 'w-24 h-24'],
  [500, 'w-28 h-28'],
  [Infinity, 'w-32 h-32'],
] as const

function sizeClass(count: number): string {
  for (const [threshold, cls] of SIZE_SCALE) {
    if (count <= threshold) return cls
  }
  return 'w-32 h-32'
}

function ClusterNode({ data }: NodeProps<ClusterNodeData>) {
  return (
    <div
      className={`rounded-lg ring-2 ${STATUS_RING[data.status]} bg-slate-800/80 ${sizeClass(
        data.taskCount
      )} flex flex-col items-center justify-center transition-all duration-500 shadow-md cursor-pointer hover:ring-4`}
    >
      <Handle type="target" position={Position.Top} className="!bg-slate-500" />

      <div className="text-[10px] text-slate-400 text-center leading-tight px-1">
        {data.complexity}
      </div>
      <div className="text-sm font-bold text-slate-200">{data.taskCount}</div>
      <div className="text-[10px] text-slate-500">${data.cost.toFixed(0)}</div>

      <Handle type="source" position={Position.Bottom} className="!bg-slate-500" />
    </div>
  )
}

export default memo(ClusterNode)
