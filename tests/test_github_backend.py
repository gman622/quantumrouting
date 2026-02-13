"""Tests for quantum_routing.github_backend -- companion issue creation.

Also tests the /api/staff and /api/materialize endpoints from intent_ide.app.
"""

from unittest.mock import patch, MagicMock
import subprocess
import json

import pytest

from quantum_routing.github_backend import (
    COMPANION_AGENTS,
    AGENT_LABEL_COLORS,
    ensure_agent_labels,
    create_companion_issues,
    post_comment,
    GitHubProgressReporter,
    _build_issue_body,
    _extract_issue_number,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_staffing_plan(profiles=None):
    """Create a minimal staffing plan for testing."""
    if profiles is None:
        profiles = [
            ("feature-trailblazer", "ticket-1-implement"),
            ("tenacious-unit-tester", "ticket-1-test"),
            ("docs-logs-wizard", "ticket-1-docs"),
            ("code-ace-reviewer", "ticket-1-review"),
        ]

    intents = []
    for profile, intent_id in profiles:
        intents.append({
            "id": intent_id,
            "profile": profile,
            "model": "gemini",
            "complexity": "moderate",
            "estimated_tokens": 1000,
            "estimated_cost": 0.005,
            "depends_on": [],
            "wave": 0,
        })

    return {
        "total_intents": len(intents),
        "total_waves": 1,
        "peak_parallelism": len(intents),
        "serial_depth": 1,
        "total_estimated_cost": 0.02,
        "total_estimated_tokens": 4000,
        "profile_load": {p: 1 for p, _ in profiles},
        "waves": [{"wave": 0, "agents_needed": len(intents), "intents": intents}],
    }


def _mock_gh_success(url="https://github.com/owner/repo/issues/42"):
    """Return a mock subprocess result for successful gh issue create."""
    mock = MagicMock()
    mock.returncode = 0
    mock.stdout = url + "\n"
    mock.stderr = ""
    return mock


def _mock_gh_failure(msg="permission denied"):
    mock = MagicMock()
    mock.returncode = 1
    mock.stdout = ""
    mock.stderr = msg
    return mock


# ---------------------------------------------------------------------------
# ensure_agent_labels
# ---------------------------------------------------------------------------

class TestEnsureAgentLabels:
    @patch("quantum_routing.github_backend.subprocess.run")
    def test_creates_labels_for_all_profiles(self, mock_run):
        mock_run.return_value = _mock_gh_success()

        results = ensure_agent_labels()

        assert mock_run.call_count == len(AGENT_LABEL_COLORS)
        for profile in AGENT_LABEL_COLORS:
            assert results[profile] is True

    @patch("quantum_routing.github_backend.subprocess.run")
    def test_uses_force_flag(self, mock_run):
        mock_run.return_value = _mock_gh_success()

        ensure_agent_labels()

        for call in mock_run.call_args_list:
            cmd = call[0][0]
            assert "--force" in cmd

    @patch("quantum_routing.github_backend.subprocess.run")
    def test_passes_repo_flag(self, mock_run):
        mock_run.return_value = _mock_gh_success()

        ensure_agent_labels(repo="octocat/hello")

        for call in mock_run.call_args_list:
            cmd = call[0][0]
            assert "--repo" in cmd
            repo_idx = cmd.index("--repo")
            assert cmd[repo_idx + 1] == "octocat/hello"

    @patch("quantum_routing.github_backend.subprocess.run")
    def test_handles_permission_error(self, mock_run):
        mock_run.return_value = _mock_gh_failure("permission denied")

        results = ensure_agent_labels()

        for profile in AGENT_LABEL_COLORS:
            assert results[profile] is False

    @patch("quantum_routing.github_backend.subprocess.run")
    def test_correct_colors(self, mock_run):
        mock_run.return_value = _mock_gh_success()

        ensure_agent_labels()

        for call in mock_run.call_args_list:
            cmd = call[0][0]
            if "--color" in cmd:
                color_idx = cmd.index("--color")
                color = cmd[color_idx + 1]
                # Must be a valid 6-char hex color
                assert len(color) == 6
                int(color, 16)  # should not raise


# ---------------------------------------------------------------------------
# create_companion_issues
# ---------------------------------------------------------------------------

class TestCreateCompanionIssues:
    @patch("quantum_routing.github_backend.subprocess.run")
    def test_creates_four_issues(self, mock_run):
        """Should create exactly 4 companion issues + 1 summary comment."""
        issue_counter = [20]

        def side_effect(cmd, **kwargs):
            if "issue" in cmd and "create" in cmd:
                issue_counter[0] += 1
                return _mock_gh_success(
                    f"https://github.com/owner/repo/issues/{issue_counter[0]}"
                )
            # Comment
            return _mock_gh_success()

        mock_run.side_effect = side_effect
        plan = _make_staffing_plan()

        created = create_companion_issues(
            parent_issue_number=20,
            parent_title="Add caching to API",
            staffing_plan=plan,
        )

        assert len(created) == 4
        assert set(created.keys()) == set(COMPANION_AGENTS)

    @patch("quantum_routing.github_backend.subprocess.run")
    def test_issue_titles_contain_agent_and_parent(self, mock_run):
        titles = []
        issue_counter = [10]

        def side_effect(cmd, **kwargs):
            if "issue" in cmd and "create" in cmd:
                issue_counter[0] += 1
                title_idx = cmd.index("--title") + 1
                titles.append(cmd[title_idx])
                return _mock_gh_success(
                    f"https://github.com/owner/repo/issues/{issue_counter[0]}"
                )
            return _mock_gh_success()

        mock_run.side_effect = side_effect

        create_companion_issues(
            parent_issue_number=10,
            parent_title="Fix auth bug",
            staffing_plan=_make_staffing_plan(),
        )

        assert len(titles) == 4
        for title in titles:
            assert "Fix auth bug" in title
            assert title.startswith("[Agent: ")

    @patch("quantum_routing.github_backend.subprocess.run")
    def test_reviewer_body_has_blocked_by(self, mock_run):
        bodies = []
        issue_counter = [0]

        def side_effect(cmd, **kwargs):
            if "issue" in cmd and "create" in cmd:
                issue_counter[0] += 1
                body_idx = cmd.index("--body") + 1
                bodies.append(cmd[body_idx])
                return _mock_gh_success(
                    f"https://github.com/owner/repo/issues/{issue_counter[0]}"
                )
            return _mock_gh_success()

        mock_run.side_effect = side_effect

        create_companion_issues(
            parent_issue_number=99,
            parent_title="Test",
            staffing_plan=_make_staffing_plan(),
        )

        # Last body is code-ace-reviewer
        reviewer_body = bodies[-1]
        assert "Blocked By" in reviewer_body
        # Should reference the other 3 issues
        assert "#1" in reviewer_body
        assert "#2" in reviewer_body
        assert "#3" in reviewer_body

    @patch("quantum_routing.github_backend.subprocess.run")
    def test_labels_match_agent_profile(self, mock_run):
        labels = []
        issue_counter = [0]

        def side_effect(cmd, **kwargs):
            if "issue" in cmd and "create" in cmd:
                issue_counter[0] += 1
                label_idx = cmd.index("--label") + 1
                labels.append(cmd[label_idx])
                return _mock_gh_success(
                    f"https://github.com/owner/repo/issues/{issue_counter[0]}"
                )
            return _mock_gh_success()

        mock_run.side_effect = side_effect

        create_companion_issues(
            parent_issue_number=1,
            parent_title="Test",
            staffing_plan=_make_staffing_plan(),
        )

        assert labels == COMPANION_AGENTS

    @patch("quantum_routing.github_backend.subprocess.run")
    def test_summary_comment_posted_on_parent(self, mock_run):
        """After creating issues, a summary comment should be posted on the parent."""
        issue_counter = [0]
        comment_calls = []

        def side_effect(cmd, **kwargs):
            if "issue" in cmd and "create" in cmd:
                issue_counter[0] += 1
                return _mock_gh_success(
                    f"https://github.com/owner/repo/issues/{issue_counter[0]}"
                )
            if "issue" in cmd and "comment" in cmd:
                comment_calls.append(cmd)
                return _mock_gh_success()
            return _mock_gh_success()

        mock_run.side_effect = side_effect

        create_companion_issues(
            parent_issue_number=50,
            parent_title="Big feature",
            staffing_plan=_make_staffing_plan(),
        )

        assert len(comment_calls) == 1
        cmd = comment_calls[0]
        assert "50" in cmd  # parent issue number
        body_idx = cmd.index("--body") + 1
        body = cmd[body_idx]
        assert "Staffing Plan Materialized" in body

    @patch("quantum_routing.github_backend.subprocess.run")
    def test_passes_repo_through(self, mock_run):
        issue_counter = [0]

        def side_effect(cmd, **kwargs):
            if "issue" in cmd and "create" in cmd:
                issue_counter[0] += 1
                return _mock_gh_success(
                    f"https://github.com/ext/repo/issues/{issue_counter[0]}"
                )
            return _mock_gh_success()

        mock_run.side_effect = side_effect

        create_companion_issues(
            parent_issue_number=1,
            parent_title="Test",
            staffing_plan=_make_staffing_plan(),
            repo="ext/repo",
        )

        for call in mock_run.call_args_list:
            cmd = call[0][0]
            assert "--repo" in cmd
            repo_idx = cmd.index("--repo")
            assert cmd[repo_idx + 1] == "ext/repo"


# ---------------------------------------------------------------------------
# _build_issue_body
# ---------------------------------------------------------------------------

class TestBuildIssueBody:
    def test_contains_parent_reference(self):
        body = _build_issue_body("feature-trailblazer", 42, "My Feature", [])
        assert "#42" in body
        assert "My Feature" in body

    def test_contains_assigned_intents(self):
        intents = [
            {"id": "intent-a", "wave": 0, "complexity": "simple"},
            {"id": "intent-b", "wave": 1, "complexity": "moderate"},
        ]
        body = _build_issue_body("feature-trailblazer", 1, "Title", intents)
        assert "intent-a" in body
        assert "intent-b" in body
        assert "wave 0" in body
        assert "wave 1" in body

    def test_reviewer_has_extra_gates(self):
        body = _build_issue_body("code-ace-reviewer", 1, "Title", [])
        assert "Architecture review" in body

    def test_tester_has_coverage_gate(self):
        body = _build_issue_body("tenacious-unit-tester", 1, "Title", [])
        assert "Coverage delta" in body

    def test_blocked_by_section(self):
        blocked = [
            {"number": 10, "agent": "feature-trailblazer"},
            {"number": 11, "agent": "tenacious-unit-tester"},
        ]
        body = _build_issue_body("code-ace-reviewer", 1, "Title", [], blocked_by=blocked)
        assert "#10" in body
        assert "#11" in body
        assert "Blocked By" in body


# ---------------------------------------------------------------------------
# _extract_issue_number
# ---------------------------------------------------------------------------

class TestExtractIssueNumber:
    def test_standard_url(self):
        assert _extract_issue_number("https://github.com/owner/repo/issues/42") == 42

    def test_trailing_slash(self):
        assert _extract_issue_number("https://github.com/owner/repo/issues/7/") == 7

    def test_non_numeric(self):
        assert _extract_issue_number("https://github.com/owner/repo/pulls") is None

    def test_empty(self):
        assert _extract_issue_number("") is None


# ---------------------------------------------------------------------------
# post_comment
# ---------------------------------------------------------------------------

class TestPostComment:
    @patch("quantum_routing.github_backend.subprocess.run")
    def test_posts_comment(self, mock_run):
        mock_run.return_value = _mock_gh_success()

        result = post_comment(42, "Hello world")

        assert result is True
        cmd = mock_run.call_args[0][0]
        assert "comment" in cmd
        assert "42" in cmd
        assert "Hello world" in cmd

    @patch("quantum_routing.github_backend.subprocess.run")
    def test_returns_false_on_failure(self, mock_run):
        mock_run.return_value = _mock_gh_failure()

        result = post_comment(42, "Hello")

        assert result is False


# ---------------------------------------------------------------------------
# GitHubProgressReporter
# ---------------------------------------------------------------------------

class TestGitHubProgressReporter:
    @patch("quantum_routing.github_backend.post_comment")
    def test_reports_wave_completed(self, mock_comment):
        mock_comment.return_value = True
        reporter = GitHubProgressReporter(parent_issue_number=10)

        reporter("wave_completed", {
            "wave": 0, "status": "passed", "score": 95.0, "duration": 1.234,
        })

        mock_comment.assert_called_once()
        body = mock_comment.call_args[0][1]
        assert "Wave 0" in body
        assert "PASS" in body

    @patch("quantum_routing.github_backend.post_comment")
    def test_reports_execution_completed(self, mock_comment):
        mock_comment.return_value = True
        reporter = GitHubProgressReporter(parent_issue_number=10)

        reporter("execution_completed", {
            "verdict": "approved", "passed": 5, "failed": 1, "human_review": 0,
        })

        mock_comment.assert_called_once()
        body = mock_comment.call_args[0][1]
        assert "Execution Complete" in body
        assert "approved" in body

    @patch("quantum_routing.github_backend.post_comment")
    def test_ignores_other_events(self, mock_comment):
        reporter = GitHubProgressReporter(parent_issue_number=10)

        reporter("intent_started", {"intent_id": "x"})
        reporter("intent_completed", {"intent_id": "x"})
        reporter("wave_started", {"wave": 0})

        mock_comment.assert_not_called()

    @patch("quantum_routing.github_backend.post_comment")
    def test_passes_repo(self, mock_comment):
        mock_comment.return_value = True
        reporter = GitHubProgressReporter(parent_issue_number=10, repo="ext/repo")

        reporter("wave_completed", {
            "wave": 0, "status": "passed", "score": 90.0, "duration": 0.5,
        })

        _, kwargs = mock_comment.call_args
        # Third positional arg or keyword
        call_args = mock_comment.call_args
        assert call_args[0][2] == "ext/repo" or call_args[1].get("repo") == "ext/repo"


# ---------------------------------------------------------------------------
# /api/staff and /api/materialize endpoint tests
# ---------------------------------------------------------------------------

def _make_mock_ticket(id_="13", title="Wire telemetry into ViolationsDashboard"):
    """Create a mock Ticket for endpoint tests."""
    ticket = MagicMock()
    ticket.id = id_
    ticket.title = title
    ticket.body = "Some body text"
    ticket.labels = ["enhancement"]
    ticket.url = f"https://github.com/owner/repo/issues/{id_}"
    ticket.ticket_type = MagicMock()
    ticket.ticket_type.name = "FEATURE"
    return ticket


class TestApiStaffEndpoint:
    """Tests for POST /api/staff — plan-only endpoint."""

    @patch("intent_ide.app.generate_staffing_plan")
    @patch("intent_ide.app.decompose_ticket_smart")
    @patch("intent_ide.app.import_issue")
    def test_returns_staffing_plan(self, mock_import, mock_decompose, mock_staff):
        """Should return full staffing plan without creating issues."""
        # Import app inside test to avoid heavy module-level init
        from intent_ide.app import app

        mock_import.return_value = _make_mock_ticket()
        mock_decompose.return_value = [
            {"id": "t-1", "profile": "feature-trailblazer"},
        ]
        mock_staff.return_value = _make_staffing_plan()

        with app.test_client() as client:
            res = client.post('/api/staff', json={"issue_number": 13})
            data = res.get_json()

        assert res.status_code == 200
        assert data["parent_issue"] == 13
        assert data["parent_title"] == "Wire telemetry into ViolationsDashboard"
        assert "staffing_plan" in data
        assert data["staffing_plan"]["total_intents"] == 4
        assert "waves" in data["staffing_plan"]

    @patch("intent_ide.app.import_issue")
    def test_missing_issue_number(self, mock_import):
        from intent_ide.app import app

        with app.test_client() as client:
            res = client.post('/api/staff', json={})

        assert res.status_code == 400
        assert "issue_number" in res.get_json()["error"]

    @patch("intent_ide.app.import_issue")
    def test_invalid_issue_number(self, mock_import):
        from intent_ide.app import app

        with app.test_client() as client:
            res = client.post('/api/staff', json={"issue_number": "abc"})

        assert res.status_code == 400
        assert "integer" in res.get_json()["error"]

    @patch("intent_ide.app.import_issue")
    def test_issue_not_found(self, mock_import):
        from intent_ide.app import app
        mock_import.return_value = None

        with app.test_client() as client:
            res = client.post('/api/staff', json={"issue_number": 999})

        assert res.status_code == 404

    @patch("intent_ide.app.decompose_ticket_smart")
    @patch("intent_ide.app.import_issue")
    def test_no_intents(self, mock_import, mock_decompose):
        from intent_ide.app import app
        mock_import.return_value = _make_mock_ticket()
        mock_decompose.return_value = []

        with app.test_client() as client:
            res = client.post('/api/staff', json={"issue_number": 13})

        assert res.status_code == 422


class TestApiMaterializeWithPlan:
    """Tests for POST /api/materialize with pre-computed plan."""

    @patch("intent_ide.app.create_companion_issues")
    @patch("intent_ide.app.ensure_agent_labels")
    def test_accepts_pre_computed_plan(self, mock_labels, mock_create):
        """When staffing_plan and parent_title are provided, skip decompose."""
        from intent_ide.app import app

        mock_labels.return_value = {"feature-trailblazer": True}
        mock_create.return_value = {
            "feature-trailblazer": 21,
            "tenacious-unit-tester": 22,
            "docs-logs-wizard": 23,
            "code-ace-reviewer": 24,
        }
        plan = _make_staffing_plan()

        with app.test_client() as client:
            res = client.post('/api/materialize', json={
                "issue_number": 13,
                "staffing_plan": plan,
                "parent_title": "Wire telemetry",
            })
            data = res.get_json()

        assert res.status_code == 200
        assert data["parent_title"] == "Wire telemetry"
        assert len(data["companion_issues"]) == 4

    @patch("intent_ide.app.generate_staffing_plan")
    @patch("intent_ide.app.decompose_ticket_smart")
    @patch("intent_ide.app.import_issue")
    @patch("intent_ide.app.create_companion_issues")
    @patch("intent_ide.app.ensure_agent_labels")
    def test_falls_back_to_full_pipeline(self, mock_labels, mock_create,
                                          mock_import, mock_decompose, mock_staff):
        """Without staffing_plan, does full decompose+staff pipeline."""
        from intent_ide.app import app

        mock_labels.return_value = {"feature-trailblazer": True}
        mock_create.return_value = {"feature-trailblazer": 21}
        mock_import.return_value = _make_mock_ticket()
        mock_decompose.return_value = [{"id": "t-1"}]
        mock_staff.return_value = _make_staffing_plan()

        with app.test_client() as client:
            res = client.post('/api/materialize', json={"issue_number": 13})

        assert res.status_code == 200
        mock_import.assert_called_once()
        mock_decompose.assert_called_once()
        mock_staff.assert_called_once()
