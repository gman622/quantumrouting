// ── Graph types ────────────────────────────────────────────────────────

export interface NodePosition {
  x: number
  y: number
}

export interface StageNodeData {
  label: string
  stage: string
  taskCount: number
  status: Status
  counts: StatusCounts
  cost: number
  color: string
}

export interface ClusterNodeData {
  label: string
  stage: string
  complexity: string
  taskCount: number
  status: Status
  counts: StatusCounts
  cost: number
  color: string
}

export interface IntentNodeData {
  label: string
  intentIdx: number
  stage: string
  complexity: string
  status: Status
  agent: string
  cost: number
  color: string
}

export type Status = 'satisfied' | 'overkill' | 'violated'

export interface StatusCounts {
  satisfied: number
  overkill: number
  violated: number
}

// ── API response types ──────────────────────────────────────────────────

export interface GraphResponse {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface GraphNode {
  id: string
  type: string
  position: NodePosition
  data: StageNodeData | ClusterNodeData | IntentNodeData
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  animated?: boolean
  style?: Record<string, string | number>
}

export interface AssignmentsMeta {
  totalCost: number
  totalTasks: number
  assignedTasks: number
  unassignedTasks: number
  depViolations: number
  statusCounts: StatusCounts
  constraints: Constraints
}

export interface Constraints {
  quality_floor: number
  budget_cap: number
  overkill_weight: number
  dep_penalty: number
  context_bonus: number
}

export interface AgentTypeSummary {
  modelType: string
  tasks: number
  capacity: number
  cost: number
  quality: number
  tokenRate: number
  isLocal: boolean
}

export interface AgentStats {
  total_agents: number
  cloud_agents: number
  local_agents: number
  cloud_capacity: number
  local_capacity: number
  total_capacity: number
}

export interface AgentsResponse {
  agents: AgentTypeSummary[]
  stats: AgentStats
}

export interface IntentDetail {
  intent: {
    id: string
    stage: string
    complexity: string
    min_quality: number
    depends: number[]
    deadline: number
    estimated_tokens: number
    story_points: number
  }
  agentName: string | null
  agent: {
    token_rate: number
    quality: number
    capabilities: string[]
    is_local: boolean
    capacity: number
    latency: number
    model_type: string
  } | null
  cost: number
}

export interface SolverProgress {
  jobId: string
  elapsed: number
}

export interface SolverCompleted {
  jobId: string
  status: string
  elapsed: number
  error: string | null
}
