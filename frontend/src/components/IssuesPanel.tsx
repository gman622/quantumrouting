import useStore from '../store'
import type { Issue } from '../types'

const typeColors: Record<string, string> = {
  feature: 'text-purple-400 bg-purple-400/10',
  bug: 'text-red-400 bg-red-400/10',
  task: 'text-blue-400 bg-blue-400/10',
  epic: 'text-amber-400 bg-amber-400/10',
  docs: 'text-slate-400 bg-slate-400/10',
  refactor: 'text-cyan-400 bg-cyan-400/10',
}

const statusColors: Record<string, string> = {
  pending: 'bg-slate-500',
  decomposing: 'bg-yellow-500 animate-pulse',
  in_progress: 'bg-blue-500',
  completed: 'bg-green-500',
}

function IssueCard({ issue, selected, onClick }: { issue: Issue; selected: boolean; onClick: () => void }) {
  const progress = issue.intentCount > 0 ? (issue.completedCount / issue.intentCount) * 100 : 0

  return (
    <button
      onClick={onClick}
      className={`w-full text-left p-2 rounded border transition-all ${
        selected
          ? 'bg-slate-700 border-indigo-500'
          : 'bg-slate-800/50 border-slate-700 hover:border-slate-600'
      }`}
    >
      <div className="flex items-start gap-2">
        <span className={`text-[9px] px-1.5 py-0.5 rounded font-medium uppercase ${typeColors[issue.ticketType] || typeColors.task}`}>
          {issue.ticketType}
        </span>
        <span className="text-[10px] text-slate-500">#{issue.id}</span>
      </div>

      <h3 className="text-xs font-medium text-slate-200 mt-1 line-clamp-2">
        {issue.title}
      </h3>

      <div className="flex items-center gap-2 mt-2">
        {/* Progress bar */}
        <div className="flex-1 h-1 bg-slate-700 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${statusColors[issue.status]}`}
            style={{ width: `${progress}%` }}
          />
        </div>
        <span className="text-[9px] text-slate-500">
          {issue.completedCount}/{issue.intentCount}
        </span>
      </div>

      <div className="flex justify-between mt-1.5 text-[9px] text-slate-500">
        <span>{issue.intentCount} intents</span>
        <span>${issue.totalCost.toFixed(2)}</span>
      </div>
    </button>
  )
}

export default function IssuesPanel() {
  const issues = useStore((s) => s.issues)
  const issuesLoading = useStore((s) => s.issuesLoading)
  const selectedIssue = useStore((s) => s.selectedIssue)
  const setSelectedIssue = useStore((s) => s.setSelectedIssue)
  const fetchIssues = useStore((s) => s.fetchIssues)

  const features = issues.filter((i) => i.ticketType === 'feature')
  const bugs = issues.filter((i) => i.ticketType === 'bug')
  const others = issues.filter((i) => !['feature', 'bug'].includes(i.ticketType))

  return (
    <div className="flex-1 overflow-y-auto p-3">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
          Issues
        </h2>
        <button
          onClick={() => fetchIssues()}
          className="text-[10px] text-slate-500 hover:text-slate-300"
          disabled={issuesLoading}
        >
          {issuesLoading ? 'Loading...' : 'Refresh'}
        </button>
      </div>

      {issues.length === 0 && !issuesLoading && (
        <div className="text-xs text-slate-500 text-center py-4">
          No issues found.<br />
          <span className="text-[10px]">Import from GitHub to get started.</span>
        </div>
      )}

      {/* Features */}
      {features.length > 0 && (
        <div className="mb-4">
          <h3 className="text-[10px] font-medium text-purple-400 uppercase tracking-wider mb-2">
            Features ({features.length})
          </h3>
          <div className="space-y-2">
            {features.map((issue) => (
              <IssueCard
                key={issue.id}
                issue={issue}
                selected={selectedIssue?.id === issue.id}
                onClick={() => setSelectedIssue(selectedIssue?.id === issue.id ? null : issue)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Bugs */}
      {bugs.length > 0 && (
        <div className="mb-4">
          <h3 className="text-[10px] font-medium text-red-400 uppercase tracking-wider mb-2">
            Bugs ({bugs.length})
          </h3>
          <div className="space-y-2">
            {bugs.map((issue) => (
              <IssueCard
                key={issue.id}
                issue={issue}
                selected={selectedIssue?.id === issue.id}
                onClick={() => setSelectedIssue(selectedIssue?.id === issue.id ? null : issue)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Other */}
      {others.length > 0 && (
        <div>
          <h3 className="text-[10px] font-medium text-slate-400 uppercase tracking-wider mb-2">
            Other ({others.length})
          </h3>
          <div className="space-y-2">
            {others.map((issue) => (
              <IssueCard
                key={issue.id}
                issue={issue}
                selected={selectedIssue?.id === issue.id}
                onClick={() => setSelectedIssue(selectedIssue?.id === issue.id ? null : issue)}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
