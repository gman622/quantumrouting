import useStore from '../store'

export default function IntentDetail() {
  const selectedNode = useStore((s) => s.selectedNode)
  const intentDetail = useStore((s) => s.intentDetail)
  const setSelectedNode = useStore((s) => s.setSelectedNode)

  if (!selectedNode) return null

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const nodeData = selectedNode.data as any

  // If this is a stage/cluster node, show summary
  if (!intentDetail && nodeData.taskCount) {
    return (
      <div className="absolute bottom-16 left-1/2 -translate-x-1/2 z-20 bg-slate-800 border border-slate-600 rounded-lg p-4 shadow-xl min-w-[280px]">
        <div className="flex justify-between items-start mb-2">
          <h3 className="text-sm font-bold text-slate-200">{nodeData.label as string}</h3>
          <button
            onClick={() => setSelectedNode(null)}
            className="text-slate-500 hover:text-slate-300 text-xs"
          >
            x
          </button>
        </div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
          <span className="text-slate-500">Tasks</span>
          <span className="text-slate-200 font-mono">{(nodeData.taskCount as number).toLocaleString()}</span>
          <span className="text-slate-500">Status</span>
          <span className={`font-mono ${
            nodeData.status === 'satisfied' ? 'text-green-400' :
            nodeData.status === 'overkill' ? 'text-yellow-400' : 'text-red-400'
          }`}>{nodeData.status as string}</span>
          {nodeData.cost !== undefined && (
            <>
              <span className="text-slate-500">Cost</span>
              <span className="text-slate-200 font-mono">${(nodeData.cost as number).toFixed(2)}</span>
            </>
          )}
        </div>
      </div>
    )
  }

  if (!intentDetail) return null

  const { intent, agentName, agent, cost } = intentDetail

  return (
    <div className="absolute bottom-16 left-1/2 -translate-x-1/2 z-20 bg-slate-800 border border-slate-600 rounded-lg p-4 shadow-xl min-w-[340px] max-w-[420px]">
      <div className="flex justify-between items-start mb-3">
        <h3 className="text-sm font-bold text-slate-200 truncate max-w-[300px]">
          {intent.id}
        </h3>
        <button
          onClick={() => { setSelectedNode(null) }}
          className="text-slate-500 hover:text-slate-300 text-xs ml-2"
        >
          x
        </button>
      </div>

      <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
        <span className="text-slate-500">Stage</span>
        <span className="text-slate-200">{intent.stage}</span>

        <span className="text-slate-500">Complexity</span>
        <span className="text-slate-200">{intent.complexity}</span>

        <span className="text-slate-500">Min Quality</span>
        <span className="text-slate-200 font-mono">{intent.min_quality.toFixed(2)}</span>

        <span className="text-slate-500">Tokens</span>
        <span className="text-slate-200 font-mono">{intent.estimated_tokens.toLocaleString()}</span>

        <span className="text-slate-500">Story Points</span>
        <span className="text-slate-200 font-mono">{intent.story_points}</span>

        <span className="text-slate-500">Dependencies</span>
        <span className="text-slate-200 font-mono">{intent.depends.length}</span>

        <div className="col-span-2 border-t border-slate-700 my-1" />

        <span className="text-slate-500">Agent</span>
        <span className={`font-mono ${agent?.is_local ? 'text-emerald-400' : 'text-sky-400'}`}>
          {agentName ?? 'unassigned'}
        </span>

        {agent && (
          <>
            <span className="text-slate-500">Agent Quality</span>
            <span className="text-slate-200 font-mono">{agent.quality.toFixed(2)}</span>

            <span className="text-slate-500">Model Type</span>
            <span className="text-slate-200">{agent.model_type}</span>

            <span className="text-slate-500">Cost</span>
            <span className="text-slate-200 font-mono">${cost.toFixed(4)}</span>
          </>
        )}
      </div>
    </div>
  )
}
