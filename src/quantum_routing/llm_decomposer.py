"""LLM-Powered Ticket Decomposition via Ollama.

Calls a local Ollama model to decompose GitHub issues into intent graphs.
Falls back gracefully — returns None on any failure so callers can use templates.

Requires: Ollama running locally (http://localhost:11434)
Model: OLLAMA_MODEL env var or qwen2.5:3b default
"""

import json
import logging
import os
from typing import Dict, List, Optional

import requests

from quantum_routing.css_renderer_config import TOKEN_ESTIMATES

log = logging.getLogger(__name__)

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA_TIMEOUT = 60  # seconds

VALID_COMPLEXITIES = set(TOKEN_ESTIMATES.keys())  # trivial, simple, moderate, complex, very-complex, epic

DECOMPOSITION_PROMPT = """\
You are an expert software architect. Analyze this GitHub issue and decompose it
into a sequence of implementation intents (atomic units of work).

ISSUE #{number}: {title}
---
BODY:
{body}
---
LABELS: {labels}

Output ONLY a valid JSON array. No markdown fences, no commentary, just the array.

Each element must have these fields:
- "id": unique string like "ticket-{number}-<phase>" (e.g. "ticket-{number}-analyze")
- "phase": one of: analyze, design, implement, test, verify, reproduce, diagnose, fix, document, plan, refactor, review, investigate
- "complexity": one of: trivial, simple, moderate, complex, very-complex, epic
- "description": 1-2 sentence description of the work
- "depends": array of intent IDs this depends on (empty array for first intent)
- "tags": array of relevant tags (e.g. ["frontend", "testing"])

RULES:
- BUGS: reproduce -> diagnose -> fix -> test -> verify (5-8 intents)
- FEATURES: analyze -> design -> implement -> test -> document (5-12 intents)
- TASKS: investigate -> implement -> verify (3-6 intents)
- Each intent should depend on the previous in its chain
- Use the issue body to create SPECIFIC descriptions, not generic ones

Respond with the JSON array only.\
"""


def decompose_ticket_llm(ticket, model: Optional[str] = None) -> Optional[List[Dict]]:
    """Decompose a ticket using a local Ollama model.

    Args:
        ticket: A Ticket object with id, title, body, labels.
        model: Override Ollama model name.

    Returns:
        List of intent spec dicts, or None on any failure.
    """
    model = model or OLLAMA_MODEL

    prompt = DECOMPOSITION_PROMPT.format(
        number=ticket.id,
        title=ticket.title,
        body=ticket.body or "(no description)",
        labels=", ".join(ticket.labels) if ticket.labels else "(none)",
    )

    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.ConnectionError:
        log.warning("Ollama not reachable at %s — falling back to templates", OLLAMA_URL)
        return None
    except requests.Timeout:
        log.warning("Ollama timed out after %ds", OLLAMA_TIMEOUT)
        return None
    except requests.RequestException as e:
        log.warning("Ollama request failed: %s", e)
        return None

    raw = resp.json().get("response", "")

    # Parse JSON — strip markdown fences if the model wraps them
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[: text.rfind("```")]
        text = text.strip()

    try:
        intents_raw = json.loads(text)
    except json.JSONDecodeError:
        log.warning("Ollama returned invalid JSON:\n%.200s", text)
        return None

    if not isinstance(intents_raw, list) or len(intents_raw) == 0:
        log.warning("Ollama returned non-list or empty list")
        return None

    return _validate_intents(intents_raw, ticket)


def _validate_intents(intents_raw: List[Dict], ticket) -> Optional[List[Dict]]:
    """Validate and normalize LLM-produced intents.

    Returns cleaned list or None if the output is unsalvageable.
    """
    ticket_id = ticket.id
    valid_ids = set()
    result = []

    for i, raw in enumerate(intents_raw):
        if not isinstance(raw, dict):
            log.warning("Intent %d is not a dict, skipping", i)
            continue

        # Required fields
        phase = raw.get("phase")
        if not phase:
            log.warning("Intent %d missing phase, skipping", i)
            continue

        intent_id = raw.get("id") or f"ticket-{ticket_id}-{phase}"
        # Deduplicate IDs
        if intent_id in valid_ids:
            intent_id = f"{intent_id}-{i}"
        valid_ids.add(intent_id)

        # Clamp complexity
        complexity = raw.get("complexity", "moderate")
        if complexity not in VALID_COMPLEXITIES:
            complexity = "moderate"

        # Fill estimated_tokens from TOKEN_ESTIMATES
        estimated_tokens = raw.get("estimated_tokens")
        if not isinstance(estimated_tokens, (int, float)) or estimated_tokens <= 0:
            estimated_tokens = TOKEN_ESTIMATES.get(complexity, 5000)

        description = raw.get("description", f"[{ticket.title}] Phase: {phase}")
        if not description.startswith(f"[{ticket.title}]"):
            description = f"[{ticket.title}] {description}"

        depends = raw.get("depends", [])
        if not isinstance(depends, list):
            depends = []

        tags = raw.get("tags", [])
        if not isinstance(tags, list):
            tags = []

        spec = {
            "id": intent_id,
            "ticket_id": ticket_id,
            "phase": phase,
            "complexity": complexity,
            "description": description,
            "depends": depends,
            "tags": tags,
            "estimated_tokens": int(estimated_tokens),
            "sequence": i,
            "_source": "llm",
        }
        result.append(spec)

    if not result:
        log.warning("No valid intents after validation")
        return None

    # Validate dependency references — drop refs to non-existent IDs
    for spec in result:
        spec["depends"] = [d for d in spec["depends"] if d in valid_ids]

    return result
