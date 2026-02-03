import { useCallback, useMemo } from 'react'
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  type NodeMouseHandler,
  type OnMoveEnd,
} from 'reactflow'
import 'reactflow/dist/style.css'
import useStore from '../store'
import StageNode from './nodes/StageNode'
import ClusterNode from './nodes/ClusterNode'
import IntentNode from './nodes/IntentNode'
import type { GraphNode } from '../types'

const nodeTypes = {
  stageNode: StageNode,
  clusterNode: ClusterNode,
  intentNode: IntentNode,
}

const ZOOM_THRESHOLDS = [0.3, 0.6, 1.0]

export default function IntentCanvas() {
  const nodes = useStore((s) => s.nodes)
  const edges = useStore((s) => s.edges)
  const zoomLevel = useStore((s) => s.zoomLevel)
  const fetchGraph = useStore((s) => s.fetchGraph)
  const setSelectedNode = useStore((s) => s.setSelectedNode)
  const fetchIntentDetail = useStore((s) => s.fetchIntentDetail)

  const rfNodes = useMemo(() => nodes ?? [], [nodes])
  const rfEdges = useMemo(() => edges ?? [], [edges])

  const onMoveEnd: OnMoveEnd = useCallback(
    (_, viewport) => {
      const vz = viewport.zoom
      let newLevel = 0
      if (vz > ZOOM_THRESHOLDS[2]) newLevel = 3
      else if (vz > ZOOM_THRESHOLDS[1]) newLevel = 2
      else if (vz > ZOOM_THRESHOLDS[0]) newLevel = 1

      if (newLevel !== zoomLevel) {
        fetchGraph(newLevel)
      }
    },
    [zoomLevel, fetchGraph]
  )

  const onNodeClick: NodeMouseHandler = useCallback(
    (_, node) => {
      const gn = node as GraphNode
      setSelectedNode(gn)
      const data = gn.data as { intentIdx?: number }
      if (data.intentIdx !== undefined) {
        fetchIntentDetail(data.intentIdx)
      }
    },
    [setSelectedNode, fetchIntentDetail]
  )

  return (
    <div className="w-full h-full relative">
      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        nodeTypes={nodeTypes}
        onMoveEnd={onMoveEnd}
        onNodeClick={onNodeClick}
        fitView
        minZoom={0.1}
        maxZoom={2}
        defaultEdgeOptions={{ type: 'smoothstep' }}
      >
        <Background color="#1e293b" gap={20} size={1} />
        <Controls />
        <MiniMap
          nodeStrokeWidth={3}
          nodeColor={(n) => {
            const s = (n.data as { status?: string })?.status
            if (s === 'satisfied') return '#22c55e'
            if (s === 'overkill') return '#eab308'
            return '#ef4444'
          }}
        />
      </ReactFlow>

      {/* Zoom level selector */}
      <div className="absolute top-4 left-1/2 -translate-x-1/2 bg-slate-800/90 border border-slate-600 rounded-lg px-4 py-1.5 text-xs text-slate-400 flex gap-3 z-10">
        {(['Stages', 'Tiers', 'Chains', 'Detail'] as const).map((label, i) => (
          <button
            key={i}
            onClick={() => fetchGraph(i)}
            className={`px-2 py-0.5 rounded transition-colors ${
              zoomLevel === i
                ? 'bg-indigo-600 text-white'
                : 'hover:bg-slate-700 text-slate-400'
            }`}
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  )
}
