"""GitHub Backend -- create companion issues and report progress.

Materializes a staffing plan as real GitHub issues following the 4-agent
companion pattern:

    feature-trailblazer   — implements the feature
    tenacious-unit-tester — writes tests
    docs-logs-wizard      — updates documentation
    code-ace-reviewer     — final review (blocked by the other 3)

Usage (called from wave_executor or Flask endpoint):
    from quantum_routing.github_backend import (
        ensure_agent_labels,
        create_companion_issues,
        GitHubProgressReporter,
    )
"""

from __future__ import annotations

import json
import subprocess
from typing import Any, Callable, Dict, List, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COMPANION_AGENTS = [
    "feature-trailblazer",
    "tenacious-unit-tester",
    "docs-logs-wizard",
    "code-ace-reviewer",  # last — blocked by other 3
]

AGENT_LABEL_COLORS: Dict[str, str] = {
    "feature-trailblazer": "0E8A16",   # green
    "tenacious-unit-tester": "1D76DB", # blue
    "docs-logs-wizard": "D4C5F9",      # lavender
    "code-ace-reviewer": "B60205",     # red
    "bug-hunter": "FBCA04",            # yellow
    "testing-guru": "0075CA",          # dark blue
    "task-predator": "E4E669",         # light yellow
}

AGENT_DESCRIPTIONS: Dict[str, str] = {
    "feature-trailblazer": "Implements the core feature code",
    "tenacious-unit-tester": "Writes comprehensive tests",
    "docs-logs-wizard": "Updates documentation and logging",
    "code-ace-reviewer": "Final code review and approval",
    "bug-hunter": "Finds and fixes bugs",
    "testing-guru": "Advanced testing and QA",
    "task-predator": "Architecture and planning",
}


# ---------------------------------------------------------------------------
# Shell helpers
# ---------------------------------------------------------------------------

def _run_gh(args: List[str], repo: Optional[str] = None) -> subprocess.CompletedProcess:
    """Run a gh CLI command, optionally targeting a specific repo."""
    cmd = ["gh"] + args
    if repo:
        cmd.extend(["--repo", repo])
    return subprocess.run(cmd, capture_output=True, text=True)


# ---------------------------------------------------------------------------
# Label management
# ---------------------------------------------------------------------------

def ensure_agent_labels(repo: Optional[str] = None) -> Dict[str, bool]:
    """Create GitHub labels for all agent profiles.

    Uses ``gh label create --force`` so it's idempotent.

    Returns:
        Dict mapping profile name to success bool.
    """
    results: Dict[str, bool] = {}
    for profile, color in AGENT_LABEL_COLORS.items():
        description = AGENT_DESCRIPTIONS.get(profile, f"Agent profile: {profile}")
        r = _run_gh([
            "label", "create", profile,
            "--color", color,
            "--description", description,
            "--force",
        ], repo=repo)
        results[profile] = r.returncode == 0
        if r.returncode != 0 and r.stderr:
            print(f"  Warning: label '{profile}': {r.stderr.strip()}")
    return results


# ---------------------------------------------------------------------------
# Companion issue creation
# ---------------------------------------------------------------------------

def _build_issue_body(
    agent: str,
    parent_number: int,
    parent_title: str,
    intents: List[Dict[str, Any]],
    blocked_by: Optional[List[Dict[str, int]]] = None,
) -> str:
    """Build the markdown body for a companion issue."""
    lines = [
        f"Parent: #{parent_number} — {parent_title}",
        "",
        f"## Role: {agent}",
        "",
        AGENT_DESCRIPTIONS.get(agent, "Execute assigned intents."),
        "",
    ]

    # Assigned intents
    if intents:
        lines.append("## Assigned Intents")
        lines.append("")
        for intent in intents:
            wave = intent.get("wave", "?")
            complexity = intent.get("complexity", "moderate")
            lines.append(f"- **{intent['id']}** (wave {wave}, {complexity})")
        lines.append("")

    # Dependencies (for code-ace-reviewer)
    if blocked_by:
        lines.append("## Blocked By")
        lines.append("")
        for dep in blocked_by:
            lines.append(f"- #{dep['number']} ({dep['agent']})")
        lines.append("")

    # Quality gates checklist
    lines.extend([
        "## Quality Gates",
        "",
        "- [ ] All assigned intents completed",
        "- [ ] Tests pass",
        "- [ ] No regressions introduced",
    ])

    if agent == "code-ace-reviewer":
        lines.extend([
            "- [ ] All companion issues resolved",
            "- [ ] Architecture review passed",
            "- [ ] Ready for merge",
        ])
    elif agent == "tenacious-unit-tester":
        lines.extend([
            "- [ ] Coverage delta > 0",
            "- [ ] Edge cases covered",
        ])
    elif agent == "docs-logs-wizard":
        lines.extend([
            "- [ ] API docs updated",
            "- [ ] README reflects changes",
        ])

    lines.extend([
        "",
        "---",
        f"*Auto-generated by Intent IDE staffing engine*",
    ])

    return "\n".join(lines)


def create_companion_issues(
    parent_issue_number: int,
    parent_title: str,
    staffing_plan: Dict[str, Any],
    repo: Optional[str] = None,
) -> Dict[str, int]:
    """Create the 4 companion issues for a parent issue.

    Args:
        parent_issue_number: The parent GitHub issue number.
        parent_title: The parent issue title.
        staffing_plan: Output of generate_staffing_plan().
        repo: Optional "owner/repo". Uses current repo if None.

    Returns:
        Dict mapping agent profile to created issue number.
    """
    # Collect all intents from the plan, grouped by profile
    intents_by_profile: Dict[str, List[Dict[str, Any]]] = {}
    for wave in staffing_plan.get("waves", []):
        for intent in wave.get("intents", []):
            profile = intent.get("profile", "feature-trailblazer")
            intents_by_profile.setdefault(profile, []).append(intent)

    created: Dict[str, int] = {}

    # Create first 3 companion issues (non-reviewer)
    for agent in COMPANION_AGENTS[:-1]:
        agent_intents = intents_by_profile.get(agent, [])
        body = _build_issue_body(
            agent=agent,
            parent_number=parent_issue_number,
            parent_title=parent_title,
            intents=agent_intents,
        )

        title = f"[Agent: {agent}] {parent_title}"
        r = _run_gh([
            "issue", "create",
            "--title", title,
            "--body", body,
            "--label", agent,
        ], repo=repo)

        if r.returncode == 0:
            # gh issue create prints the URL; extract issue number
            url = r.stdout.strip()
            issue_num = _extract_issue_number(url)
            if issue_num:
                created[agent] = issue_num
        else:
            print(f"  Error creating {agent} issue: {r.stderr.strip()}")

    # Create code-ace-reviewer (blocked by the other 3)
    reviewer_agent = COMPANION_AGENTS[-1]
    blocked_by = [
        {"number": num, "agent": agent}
        for agent, num in created.items()
    ]
    reviewer_intents = intents_by_profile.get(reviewer_agent, [])
    body = _build_issue_body(
        agent=reviewer_agent,
        parent_number=parent_issue_number,
        parent_title=parent_title,
        intents=reviewer_intents,
        blocked_by=blocked_by,
    )

    title = f"[Agent: {reviewer_agent}] {parent_title}"
    r = _run_gh([
        "issue", "create",
        "--title", title,
        "--body", body,
        "--label", reviewer_agent,
    ], repo=repo)

    if r.returncode == 0:
        url = r.stdout.strip()
        issue_num = _extract_issue_number(url)
        if issue_num:
            created[reviewer_agent] = issue_num
    else:
        print(f"  Error creating {reviewer_agent} issue: {r.stderr.strip()}")

    # Post summary comment on parent issue
    if created:
        _post_summary_comment(
            parent_issue_number, staffing_plan, created, repo,
        )

    return created


def _extract_issue_number(url: str) -> Optional[int]:
    """Extract issue number from a GitHub URL like https://github.com/owner/repo/issues/42."""
    parts = url.rstrip("/").split("/")
    if parts and parts[-1].isdigit():
        return int(parts[-1])
    return None


def _post_summary_comment(
    parent_number: int,
    staffing_plan: Dict[str, Any],
    created: Dict[str, int],
    repo: Optional[str] = None,
) -> None:
    """Post a summary comment on the parent issue."""
    total_waves = staffing_plan.get("total_waves", 0)
    total_intents = staffing_plan.get("total_intents", 0)
    peak = staffing_plan.get("peak_parallelism", 0)
    cost = staffing_plan.get("total_estimated_cost", 0)

    issue_links = ", ".join(
        f"#{num} {agent}" for agent, num in created.items()
    )

    body = (
        f"**Staffing Plan Materialized** -- "
        f"Created {len(created)} companion issues: {issue_links}. "
        f"{total_waves} waves, {total_intents} intents, "
        f"peak parallelism {peak}, est. cost ${cost:.4f}."
    )

    post_comment(parent_number, body, repo)


# ---------------------------------------------------------------------------
# Comment posting
# ---------------------------------------------------------------------------

def post_comment(issue_number: int, body: str, repo: Optional[str] = None) -> bool:
    """Post a comment on a GitHub issue.

    Returns True on success.
    """
    r = _run_gh([
        "issue", "comment", str(issue_number),
        "--body", body,
    ], repo=repo)
    if r.returncode != 0 and r.stderr:
        print(f"  Warning: comment on #{issue_number}: {r.stderr.strip()}")
    return r.returncode == 0


# ---------------------------------------------------------------------------
# Progress reporter
# ---------------------------------------------------------------------------

class GitHubProgressReporter:
    """Posts progress comments on the parent issue at key milestones.

    Only posts on ``wave_completed`` and ``execution_completed`` events
    to avoid spamming the issue.
    """

    def __init__(self, parent_issue_number: int, repo: Optional[str] = None) -> None:
        self.parent_issue_number = parent_issue_number
        self.repo = repo

    def __call__(self, event: str, data: Dict[str, Any]) -> None:
        if event == "wave_completed":
            status = "PASS" if data.get("status") == "passed" else "FAIL"
            body = (
                f"**Wave {data.get('wave', '?')} [{status}]** -- "
                f"score={data.get('score', 0):.1f}, "
                f"duration={data.get('duration', 0):.3f}s"
            )
            post_comment(self.parent_issue_number, body, self.repo)

        elif event == "execution_completed":
            verdict = data.get("verdict", "unknown")
            passed = data.get("passed", 0)
            failed = data.get("failed", 0)
            human = data.get("human_review", 0)
            body = (
                f"**Execution Complete** -- "
                f"Verdict: {verdict}, "
                f"Passed: {passed}, Failed: {failed}, "
                f"Human review: {human}"
            )
            post_comment(self.parent_issue_number, body, self.repo)
