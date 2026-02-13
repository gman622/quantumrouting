import { create } from 'zustand'
import type {
  GraphNode,
  GraphEdge,
  AssignmentsMeta,
  Constraints,
  AgentTypeSummary,
  AgentStats,
  IntentDetail,
  Issue,
  MaterializeResult,
  StaffPlanResponse,
} from './types'

const API = ''  // proxy via vite dev server; empty string = same origin

interface Store {
  // Graph data
  nodes: GraphNode[]
  edges: GraphEdge[]
  zoomLevel: number

  // Assignment metadata
  meta: AssignmentsMeta | null
  constraints: Constraints

  // Agent summary
  agentSummary: AgentTypeSummary[]
  agentStats: AgentStats | null

  // Issues (GitHub)
  issues: Issue[]
  selectedIssue: Issue | null
  issuesLoading: boolean

  // Solver state
  solving: boolean
  solverElapsed: number
  solverJobId: string | null

  // UI state
  selectedNode: GraphNode | null
  intentDetail: IntentDetail | null
  leftPanelTab: 'issues' | 'agents' | 'staffing'
  leftPanelOpen: boolean
  githubRepo: string

  // Staffing plan (preview)
  staffingPlan: StaffPlanResponse | null
  planLoading: boolean
  planError: string | null

  // Staffing / Materialize
  materializing: boolean
  materializeResult: MaterializeResult | null
  materializeError: string | null

  // Actions
  setZoomLevel: (z: number) => void
  setSolving: (s: boolean) => void
  setSolverElapsed: (e: number) => void
  setSelectedNode: (n: GraphNode | null) => void
  setLeftPanelTab: (t: 'issues' | 'agents' | 'staffing') => void
  setLeftPanelOpen: (o: boolean) => void
  setSelectedIssue: (i: Issue | null) => void
  setGithubRepo: (repo: string) => void

  fetchGraph: (zoom?: number) => Promise<void>
  fetchAssignments: () => Promise<void>
  fetchAgents: () => Promise<void>
  fetchIntentDetail: (idx: number) => Promise<void>
  fetchIssues: () => Promise<void>
  submitSolve: (constraints: Constraints) => Promise<void>
  onSolverCompleted: () => void
  generatePlan: (issueNumber: number, repo?: string) => Promise<void>
  clearPlan: () => void
  materializeIssue: (issueNumber: number, repo?: string) => Promise<void>
}

const useStore = create<Store>((set, get) => ({
  nodes: [],
  edges: [],
  zoomLevel: 0,

  meta: null,
  constraints: {
    quality_floor: 0.0,
    budget_cap: 10000.0,
    overkill_weight: 2.0,
    dep_penalty: 100.0,
    context_bonus: 0.5,
  },

  agentSummary: [],
  agentStats: null,

  issues: [],
  selectedIssue: null,
  issuesLoading: false,

  solving: false,
  solverElapsed: 0,
  solverJobId: null,

  selectedNode: null,
  intentDetail: null,
  leftPanelTab: 'issues',
  leftPanelOpen: true,
  githubRepo: '',

  staffingPlan: null,
  planLoading: false,
  planError: null,

  materializing: false,
  materializeResult: null,
  materializeError: null,

  setZoomLevel: (z) => set({ zoomLevel: z }),
  setSolving: (s) => set({ solving: s }),
  setSolverElapsed: (e) => set({ solverElapsed: e }),
  setSelectedNode: (n) => set({ selectedNode: n }),
  setLeftPanelTab: (t) => set({ leftPanelTab: t }),
  setLeftPanelOpen: (o) => set({ leftPanelOpen: o }),
  setSelectedIssue: (i) => set({ selectedIssue: i }),
  setGithubRepo: (repo) => {
    set({ githubRepo: repo })
    // Refetch issues when repo changes
    get().fetchIssues()
  },

  fetchGraph: async (zoom) => {
    const level = zoom !== undefined ? zoom : get().zoomLevel
    try {
      const res = await fetch(`${API}/api/graph?zoom=${level}`)
      const data = await res.json()
      set({ nodes: data.nodes, edges: data.edges, zoomLevel: level })
    } catch (err) {
      console.error('Failed to fetch graph:', err)
    }
  },

  fetchAssignments: async () => {
    try {
      const res = await fetch(`${API}/api/assignments`)
      const data = await res.json()
      set({ meta: data, constraints: data.constraints ?? get().constraints })
    } catch (err) {
      console.error('Failed to fetch assignments:', err)
    }
  },

  fetchAgents: async () => {
    try {
      const res = await fetch(`${API}/api/agents`)
      const data = await res.json()
      set({ agentSummary: data.agents, agentStats: data.stats })
    } catch (err) {
      console.error('Failed to fetch agents:', err)
    }
  },

  fetchIntentDetail: async (idx) => {
    try {
      const res = await fetch(`${API}/api/intent/${idx}`)
      const data = await res.json()
      set({ intentDetail: data })
    } catch (err) {
      console.error('Failed to fetch intent detail:', err)
    }
  },

  fetchIssues: async () => {
    set({ issuesLoading: true })
    try {
      const repo = get().githubRepo
      const url = repo ? `/api/issues?repo=${encodeURIComponent(repo)}` : '/api/issues'
      const res = await fetch(url)
      const data = await res.json()
      set({ issues: data.issues, issuesLoading: false })
    } catch (err) {
      console.error('Failed to fetch issues:', err)
      set({ issuesLoading: false })
    }
  },

  submitSolve: async (constraints) => {
    set({ solving: true, solverElapsed: 0 })
    try {
      const res = await fetch(`${API}/api/solve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(constraints),
      })
      const data = await res.json()
      set({ solverJobId: data.jobId, constraints })
    } catch (err) {
      console.error('Failed to submit solve:', err)
      set({ solving: false })
    }
  },

  onSolverCompleted: () => {
    set({ solving: false })
    get().fetchGraph()
    get().fetchAssignments()
    get().fetchAgents()
  },

  generatePlan: async (issueNumber, repo) => {
    set({ planLoading: true, staffingPlan: null, planError: null, materializeResult: null, materializeError: null })
    try {
      const res = await fetch(`${API}/api/staff`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          issue_number: issueNumber,
          repo: repo || get().githubRepo || undefined,
        }),
      })
      const data = await res.json()
      if (!res.ok) {
        set({ planLoading: false, planError: data.error || 'Unknown error' })
        return
      }
      set({ planLoading: false, staffingPlan: data })
    } catch (err) {
      console.error('Failed to generate plan:', err)
      set({ planLoading: false, planError: String(err) })
    }
  },

  clearPlan: () => {
    set({ staffingPlan: null, planError: null, materializeResult: null, materializeError: null })
  },

  materializeIssue: async (issueNumber, repo) => {
    set({ materializing: true, materializeResult: null, materializeError: null })
    try {
      const plan = get().staffingPlan
      const body: Record<string, unknown> = {
        issue_number: issueNumber,
        repo: repo || get().githubRepo || undefined,
      }
      // If we have a pre-computed plan, pass it through to skip re-decomposition
      if (plan) {
        body.staffing_plan = plan.staffing_plan
        body.parent_title = plan.parent_title
      }
      const res = await fetch(`${API}/api/materialize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json()
      if (!res.ok) {
        set({ materializing: false, materializeError: data.error || 'Unknown error' })
        return
      }
      set({ materializing: false, materializeResult: data })
      // Refresh issues list since new ones were created
      get().fetchIssues()
    } catch (err) {
      console.error('Failed to materialize:', err)
      set({ materializing: false, materializeError: String(err) })
    }
  },
}))

export default useStore
