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

// ── Wave Diff Types ─────────────────────────────────────────────────────

// Intent delta from a wave execution
export interface IntentDelta {
  intentId: string
  title: string
  status: 'success' | 'warning' | 'failed'
  agent: string
  agentModel: string
  changes: FileChange[]
  warnings: string[]
  errors: string[]
}

// File change within an intent
export interface FileChange {
  filePath: string
  changeType: 'created' | 'modified' | 'deleted'
  logicSummary: string
  boilerplateSuppressed: boolean
  rawDiff?: string
}

// Metric values before/after wave
export interface MetricSnapshot {
  p99Latency: number
  avgLatency: number
  testCoverage: number
  tokenCost: number
  chainCoherence: number
  gatePassRate: number
  dependencyCount: number
}

// Metric change (delta)
export interface MetricDelta {
  name: string
  before: number
  after: number
  change: number
  changeType: 'improvement' | 'regression' | 'neutral'
  severity: 'warning' | 'success' | 'info'
}

// Impact prediction for a file
export interface ImpactPrediction {
  filePath: string
  riskLevel: 'high' | 'medium' | 'low'
  predictedImpact: string[]
  affectedMetrics: string[]
}

// Complete wave data for diff
export interface WaveData {
  waveId: string
  intentDeltas: IntentDelta[]
  filesChanged: number
  files: string[]
  metricsBefore: MetricSnapshot
  metricsAfter: MetricSnapshot
  metricDeltas: MetricDelta[]
  impactPredictions: ImpactPrediction[]
}

// Constraint HUD display data
export interface ConstraintHUDData {
  metrics: MetricDelta[]
  isAnyRegression: boolean
  isAllImproved: boolean
}

// ── GitHub Issues ──────────────────────────────────────────────────────

export type TicketType = 'feature' | 'bug' | 'task' | 'epic' | 'docs' | 'refactor'

export interface Issue {
  id: string
  title: string
  body: string
  labels: string[]
  ticketType: TicketType
  url: string
  intentIds: string[]
  intentCount: number
  completedCount: number
  totalCost: number
  status: 'pending' | 'decomposing' | 'in_progress' | 'completed'
}

export interface IssuesResponse {
  issues: Issue[]
  total: number
}
