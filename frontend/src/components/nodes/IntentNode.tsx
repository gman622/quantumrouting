import { memo } from 'react'
import { Handle, Position, type NodeProps } from 'reactflow'
import type { IntentNodeData } from '../../types'

const STATUS_COLOR = {
  satisfied: 'bg-green-500',
  overkill: 'bg-yellow-500',
  violated: 'bg-red-500',
} as const

const STATUS_BORDER = {
  satisfied: 'border-green-500/40',
  overkill: 'border-yellow-500/40',
  violated: 'border-red-500/40',
} as const

function IntentNode({ data }: NodeProps<IntentNodeData>) {
  return (
    <div
      className={`rounded-md border ${STATUS_BORDER[data.status]} bg-slate-800/90 px-2 py-1 min-w-[100px] shadow transition-all duration-500 cursor-pointer hover:brightness-125`}
    >
      <Handle type="target" position={Position.Left} className="!bg-slate-500 !w-1.5 !h-1.5" />

      <div className="flex items-center gap-1.5">
        <div className={`w-2 h-2 rounded-full ${STATUS_COLOR[data.status]} transition-colors duration-500`} />
        <span className="text-[9px] text-slate-300 truncate max-w-[80px]">
          {data.label}
        </span>
      </div>
      <div className="text-[8px] text-slate-500 mt-0.5 flex justify-between">
        <span>{data.complexity}</span>
        <span>{data.agent?.split('-')[0] ?? '?'}</span>
      </div>

      <Handle type="source" position={Position.Right} className="!bg-slate-500 !w-1.5 !h-1.5" />
    </div>
  )
}

export default memo(IntentNode)
