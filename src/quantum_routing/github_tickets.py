"""GitHub Issues → Intent Graph integration.

Import GitHub issues as tickets, decompose into intents, track status.
"""

import json
import subprocess
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import Enum, auto


class TicketType(Enum):
    """Inferred from GitHub labels."""
    FEATURE = auto()
    BUG = auto()
    TASK = auto()
    EPIC = auto()
    DOCS = auto()
    REFACTOR = auto()


@dataclass
class Ticket:
    """A GitHub issue mapped to an intent subgraph."""
    id: str                              # "123" (issue number)
    repo: str                            # "owner/repo"
    title: str
    body: str
    labels: List[str] = field(default_factory=list)
    ticket_type: TicketType = TicketType.TASK
    intent_ids: List[str] = field(default_factory=list)

    @property
    def url(self) -> str:
        return f"https://github.com/{self.repo}/issues/{self.id}"

    @property
    def status(self) -> str:
        """Derived from intent statuses."""
        if not self.intent_ids:
            return "pending_decomposition"
        # Would check actual intent statuses here
        return "in_progress"

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'repo': self.repo,
            'title': self.title,
            'body': self.body,
            'labels': self.labels,
            'type': self.ticket_type.name,
            'intent_ids': self.intent_ids,
            'url': self.url,
        }


def infer_ticket_type(labels: List[str]) -> TicketType:
    """Infer ticket type from GitHub labels."""
    labels_lower = [l.lower() for l in labels]

    if any(l in labels_lower for l in ['bug', 'fix', 'bugfix']):
        return TicketType.BUG
    if any(l in labels_lower for l in ['feature', 'enhancement', 'feat']):
        return TicketType.FEATURE
    if any(l in labels_lower for l in ['epic', 'initiative']):
        return TicketType.EPIC
    if any(l in labels_lower for l in ['docs', 'documentation']):
        return TicketType.DOCS
    if any(l in labels_lower for l in ['refactor', 'tech-debt', 'cleanup']):
        return TicketType.REFACTOR

    return TicketType.TASK


def gh_issue_list(repo: Optional[str] = None, state: str = "open", limit: int = 100) -> List[Dict]:
    """Fetch issues from GitHub using gh CLI.

    Args:
        repo: Optional "owner/repo" string. Uses current repo if None.
        state: "open", "closed", or "all"
        limit: Max issues to fetch

    Returns:
        List of issue dicts with number, title, body, labels, state
    """
    cmd = [
        "gh", "issue", "list",
        "--state", state,
        "--limit", str(limit),
        "--json", "number,title,body,labels,state"
    ]
    if repo:
        cmd.extend(["--repo", repo])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        issues = json.loads(result.stdout)
        return issues
    except subprocess.CalledProcessError as e:
        print(f"Error fetching issues: {e.stderr}")
        return []
    except json.JSONDecodeError:
        print("Error parsing GitHub response")
        return []


def gh_issue_get(issue_number: int, repo: Optional[str] = None) -> Optional[Dict]:
    """Fetch a single issue with full details."""
    cmd = [
        "gh", "issue", "view", str(issue_number),
        "--json", "number,title,body,labels,state,comments,assignees"
    ]
    if repo:
        cmd.extend(["--repo", repo])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None


def import_issue(issue_number: int, repo: Optional[str] = None) -> Optional[Ticket]:
    """Import a GitHub issue as a Ticket."""
    issue = gh_issue_get(issue_number, repo)
    if not issue:
        return None

    labels = [l['name'] for l in issue.get('labels', [])]

    return Ticket(
        id=str(issue['number']),
        repo=repo or _get_current_repo(),
        title=issue['title'],
        body=issue.get('body', ''),
        labels=labels,
        ticket_type=infer_ticket_type(labels),
    )


def import_all_issues(repo: Optional[str] = None, state: str = "open") -> List[Ticket]:
    """Import all open issues as Tickets."""
    issues = gh_issue_list(repo, state)
    tickets = []

    for issue in issues:
        labels = [l['name'] for l in issue.get('labels', [])]
        ticket = Ticket(
            id=str(issue['number']),
            repo=repo or _get_current_repo(),
            title=issue['title'],
            body=issue.get('body', ''),
            labels=labels,
            ticket_type=infer_ticket_type(labels),
        )
        tickets.append(ticket)

    return tickets


def _get_current_repo() -> str:
    """Get the current repo from git remote."""
    try:
        result = subprocess.run(
            ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return "unknown/unknown"


# ══════════════════════════════════════════════════════════════════════════════
# DECOMPOSITION TEMPLATES
# ══════════════════════════════════════════════════════════════════════════════

DECOMPOSITION_TEMPLATES = {
    TicketType.FEATURE: [
        ("analyze", "trivial", "Analyze requirements and identify affected components"),
        ("design", "simple", "Design the implementation approach"),
        ("implement", "moderate", "Implement the core functionality"),
        ("test", "simple", "Write tests for the new feature"),
        ("document", "trivial", "Update documentation"),
    ],
    TicketType.BUG: [
        ("reproduce", "trivial", "Create minimal reproduction case"),
        ("diagnose", "simple", "Identify root cause"),
        ("fix", "moderate", "Implement the fix"),
        ("test", "simple", "Add regression test"),
    ],
    TicketType.REFACTOR: [
        ("analyze", "simple", "Analyze current implementation"),
        ("plan", "simple", "Plan refactoring steps"),
        ("refactor", "moderate", "Execute refactoring"),
        ("verify", "simple", "Verify behavior unchanged"),
    ],
    TicketType.DOCS: [
        ("review", "trivial", "Review current documentation"),
        ("write", "simple", "Write/update documentation"),
        ("verify", "trivial", "Verify accuracy"),
    ],
    TicketType.TASK: [
        ("implement", "simple", "Complete the task"),
        ("verify", "trivial", "Verify completion"),
    ],
    TicketType.EPIC: [
        ("decompose", "moderate", "Break down into sub-features"),
        ("prioritize", "simple", "Prioritize sub-features"),
        # Epics spawn more tickets, not just intents
    ],
}


def decompose_ticket(ticket: Ticket) -> List[Dict]:
    """Decompose a ticket into intent specifications.

    Returns list of intent specs (not full Intent objects - those come from
    the main intent generator with proper IDs and routing).
    """
    template = DECOMPOSITION_TEMPLATES.get(ticket.ticket_type, DECOMPOSITION_TEMPLATES[TicketType.TASK])

    intents = []
    for i, (phase, complexity, description) in enumerate(template):
        intent_spec = {
            'id': f"ticket-{ticket.id}-{phase}",
            'ticket_id': ticket.id,
            'phase': phase,
            'complexity': complexity,
            'description': f"[{ticket.title}] {description}",
            'sequence': i,
            'depends': [f"ticket-{ticket.id}-{template[i-1][0]}"] if i > 0 else [],
        }
        intents.append(intent_spec)

    return intents


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    import sys

    print("GitHub Issues → Intent Graph")
    print("=" * 60)

    # Try to list issues from current repo
    print("\nFetching open issues...")
    tickets = import_all_issues(state="open")

    if not tickets:
        print("No issues found (or gh CLI not configured)")
        sys.exit(0)

    print(f"Found {len(tickets)} open issues:\n")

    for ticket in tickets[:10]:  # Show first 10
        print(f"#{ticket.id}: {ticket.title}")
        print(f"    Type: {ticket.ticket_type.name}")
        print(f"    Labels: {', '.join(ticket.labels) or '(none)'}")

        # Show decomposition
        intents = decompose_ticket(ticket)
        print(f"    Decomposes into {len(intents)} intents:")
        for intent in intents:
            print(f"      - [{intent['complexity']}] {intent['phase']}: {intent['description'][:50]}...")
        print()

    print(f"\nTotal: {len(tickets)} tickets → {sum(len(decompose_ticket(t)) for t in tickets)} intents")
