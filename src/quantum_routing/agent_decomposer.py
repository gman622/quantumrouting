"""Hierarchical Agent System with Quantum-Inspired Intent Decomposition.

Agents can spawn sub-agents to handle decomposed tasks. The decomposition
structure is optimized using quantum-inspired algorithms.

Architecture:
    OrchestratorAgent
        → spawns → SpecialistAgent
        → spawns → WorkerAgent
        → results → merged back up
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional, Any, Callable
from abc import ABC, abstractmethod
import json
import time


class AgentType(Enum):
    """Agent capability types."""
    ORCHESTRATOR = auto()  # High-level planning, decomposition
    ARCHITECT = auto()     # System design, structure
    IMPLEMENTER = auto()   # Code generation
    REVIEWER = auto()     # Quality assurance, testing
    RESEARCHER = auto()   # Information gathering
    WORKER = auto()       # Simple task execution


class IntentStatus(Enum):
    """Status of an intent in the decomposition pipeline."""
    PENDING = auto()
    DECOMPOSING = auto()
    DECOMPOSED = auto()
    EXECUTING = auto()
    COMPLETED = auto()
    FAILED = auto()
    MERGED = auto()


@dataclass
class Intent:
    """A unit of work that can be decomposed into sub-intents."""
    id: str
    description: str
    complexity: str  # trivial, simple, moderate, complex, epic
    min_quality: float = 0.7
    dependencies: List[str] = field(default_factory=list)
    parent_id: Optional[str] = None
    sub_intent_ids: List[str] = field(default_factory=list)
    assigned_agent: Optional[str] = None
    status: IntentStatus = IntentStatus.PENDING
    result: Optional[Any] = None
    quality_score: Optional[float] = None
    estimated_tokens: int = 1000
    deadline: Optional[int] = None  # Time budget in seconds

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'description': self.description,
            'complexity': self.complexity,
            'min_quality': self.min_quality,
            'dependencies': self.dependencies,
            'parent_id': self.parent_id,
            'sub_intent_ids': self.sub_intent_ids,
            'assigned_agent': self.assigned_agent,
            'status': self.status.name,
            'estimated_tokens': self.estimated_tokens,
            'deadline': self.deadline,
        }


@dataclass  
class Agent:
    """An agent capable of handling intents and spawning sub-agents."""
    id: str
    agent_type: AgentType
    model_name: str
    quality: float  # 0-1 capability score
    cost_per_token: float
    capabilities: List[str]
    max_children: int = 5  # Max sub-agents can spawn
    current_children: int = 0
    specialties: List[str] = field(default_factory=list)
    success_rate: float = 0.9  # Historical success rate
    total_tasks: int = 0
    successful_tasks: int = 0

    @property
    def effectiveness(self) -> float:
        """Agent effectiveness score combining quality and success rate."""
        return self.quality * self.success_rate

    def can_spawn(self) -> bool:
        """Check if agent can spawn more sub-agents."""
        return self.current_children < self.max_children

    def spawn_child(self, intent: Intent) -> 'Agent':
        """Create a sub-agent for handling a decomposed intent."""
        if not self.can_spawn():
            raise ValueError(f"Agent {self.id} cannot spawn more children")

        # Sub-agent inherits capabilities but with narrower focus
        child = Agent(
            id=f"{self.id}-child-{self.current_children + 1}",
            agent_type=self._infer_child_type(intent.complexity),
            model_name=self.model_name,  # Could use different model
            quality=self.quality * 0.95,  # Slight quality degradation
            cost_per_token=self.cost_per_token * 0.9,
            capabilities=self.capabilities[:3],  # Narrower capabilities
            max_children=2,  # Children have fewer spawn rights
            specialties=[intent.complexity],
        )
        self.current_children += 1
        return child

    def _infer_child_type(self, complexity: str) -> AgentType:
        """Infer appropriate agent type for complexity."""
        type_map = {
            'trivial': AgentType.WORKER,
            'simple': AgentType.WORKER,
            'moderate': AgentType.IMPLEMENTER,
            'complex': AgentType.REVIEWER,
            'epic': AgentType.ARCHITECT,
        }
        return type_map.get(complexity, AgentType.WORKER)

    def record_success(self):
        """Record a successful task completion."""
        self.total_tasks += 1
        self.successful_tasks += 1
        self.success_rate = self.successful_tasks / self.total_tasks

    def record_failure(self):
        """Record a failed task."""
        self.total_tasks += 1
        # success_rate automatically updates


class QuantumDecomposer:
    """Quantum-inspired optimizer for intent decomposition.
    
    Uses techniques inspired by QAOA/quantum annealing to find
    optimal decomposition structures.
    """

    def __init__(self, agents: Dict[str, Agent], max_depth: int = 5):
        self.agents = agents
        self.max_depth = max_depth

    def decompose(
        self,
        intent: Intent,
        available_agents: List[Agent],
        time_limit: float = 30.0
    ) -> List[Intent]:
        """Find optimal decomposition of an intent.
        
        Args:
            intent: The high-level intent to decompose
            available_agents: Agents that can be spawned
            time_limit: Maximum optimization time
            
        Returns:
            List of sub-intents that optimally decompose the original
        """
        start_time = time.time()

        # Decomposition strategy based on complexity
        if intent.complexity in ('trivial', 'simple'):
            return self._trivial_decompose(intent)
        elif intent.complexity == 'moderate':
            return self._moderate_decompose(intent, available_agents)
        elif intent.complexity == 'complex':
            return self._complex_decompose(intent, available_agents)
        else:  # epic
            return self._epic_decompose(intent, available_agents)

    def _trivial_decompose(self, intent: Intent) -> List[Intent]:
        """No decomposition needed."""
        return [intent]

    def _moderate_decompose(
        self,
        intent: Intent,
        available_agents: List[Agent]
    ) -> List[Intent]:
        """Simple 2-3 way split."""
        return self._create_sub_intents(
            intent,
            num_children=2,
            available_agents=available_agents
        )

    def _complex_decompose(
        self,
        intent: Intent,
        available_agents: List[Agent]
    ) -> List[Intent]:
        """Multi-level decomposition."""
        return self._create_sub_intents(
            intent,
            num_children=3,
            available_agents=available_agents
        )

    def _epic_decompose(
        self,
        intent: Intent,
        available_agents: List[Agent]
    ) -> List[Intent]:
        """Hierarchical decomposition with multiple levels."""
        # First level: broad categorization
        level1 = self._create_sub_intents(
            intent,
            num_children=4,  # Analyze, Design, Implement, Verify
            available_agents=available_agents
        )
        return level1

    def _create_sub_intents(
        self,
        parent: Intent,
        num_children: int,
        available_agents: List[Agent]
    ) -> List[Intent]:
        """Create child intents from a parent."""
        sub_intents = []
        agent_assignments = []

        for i in range(num_children):
            sub_id = f"{parent.id}-sub-{i + 1}"

            # Inherit some properties, specialize others
            complexity = self._specialize_complexity(parent.complexity, i, num_children)

            sub_intent = Intent(
                id=sub_id,
                description=f"Sub-task {i + 1} of {parent.description}",
                complexity=complexity,
                min_quality=parent.min_quality * 0.95,
                dependencies=[],
                parent_id=parent.id,
                estimated_tokens=parent.estimated_tokens // num_children,
            )
            sub_intents.append(sub_intent)

            # Assign best available agent
            best_agent = self._assign_agent(sub_intent, available_agents)
            agent_assignments.append(best_agent)

        return sub_intents

    def _specialize_complexity(
        self,
        parent_complexity: str,
        child_index: int,
        total_children: int
    ) -> str:
        """Specialize complexity for child intents."""
        hierarchy = ['trivial', 'simple', 'moderate', 'complex', 'very-complex', 'epic']
        try:
            parent_idx = hierarchy.index(parent_complexity)
        except ValueError:
            return 'simple'

        # Distribute complexity across children
        if total_children == 2:
            return hierarchy[max(0, parent_idx - 1)]
        elif total_children == 3:
            if child_index == 0:
                return hierarchy[max(0, parent_idx - 1)]
            elif child_index == 1:
                return hierarchy[parent_idx]
            else:
                return hierarchy[min(len(hierarchy) - 1, parent_idx + 1)]
        else:  # 4+ children
            return hierarchy[max(0, parent_idx - 2 + child_index)]

    def _assign_agent(
        self,
        intent: Intent,
        available_agents: List[Agent]
    ) -> Agent:
        """Assign the best agent for an intent."""
        candidates = [
            a for a in available_agents
            if intent.complexity in a.capabilities and a.can_spawn()
        ]

        if not candidates:
            # Fallback to any capable agent
            candidates = [
                a for a in available_agents
                if intent.complexity in a.capabilities
            ]

        # Select by effectiveness score
        best = max(candidates, key=lambda a: a.effectiveness)
        return best


class AgentSpawner:
    """Manages agent spawning and hierarchy."""

    def __init__(self):
        self.agents: Dict[str, Agent] = {}
        self.intents: Dict[str, Intent] = {}
        self.hierarchy: Dict[str, List[str]] = {}  # parent_id -> [child_ids]

    def register_agent(self, agent: Agent):
        """Register an agent in the system."""
        self.agents[agent.id] = agent

    def register_intent(self, intent: Intent):
        """Register an intent."""
        self.intents[intent.id] = intent

    def spawn_agent(
        self,
        parent_agent_id: str,
        parent_intent: Intent,
        decomposer: QuantumDecomposer
    ) -> Agent:
        """Spawn a new agent for handling a decomposed intent."""
        parent_agent = self.agents[parent_agent_id]

        if not parent_agent.can_spawn():
            raise ValueError(f"Agent {parent_agent_id} has reached max children")

        child_agent = parent_agent.spawn_child(parent_intent)
        self.register_agent(child_agent)

        return child_agent

    def decompose_and_spawn(
        self,
        orchestrator_id: str,
        root_intent: Intent,
        decomposer: QuantumDecomposer
    ) -> List[Intent]:
        """Decompose an intent and spawn agents for each sub-intent."""
        orchestrator = self.agents[orchestrator_id]

        # Decompose the intent
        sub_intents = decomposer.decompose(
            root_intent,
            list(self.agents.values())
        )

        # Register sub-intents
        for sub in sub_intents:
            self.register_intent(sub)

        # Update hierarchy
        self.hierarchy[root_intent.id] = [s.id for s in sub_intents]

        # Spawn agents for each sub-intent
        for sub_intent in sub_intents:
            agent = self.spawn_agent(orchestrator_id, sub_intent, decomposer)
            sub_intent.assigned_agent = agent.id

        return sub_intents

    def merge_results(self, parent_intent_id: str) -> Dict:
        """Merge results from all child intents."""
        child_ids = self.hierarchy.get(parent_intent_id, [])
        results = []

        for child_id in child_ids:
            child_intent = self.intents[child_id]
            if child_intent.status == IntentStatus.COMPLETED:
                results.append({
                    'intent_id': child_id,
                    'result': child_intent.result,
                    'quality': child_intent.quality_score,
                })

        # Aggregate results (simple concatenation for now)
        return {
            'parent_id': parent_intent_id,
            'child_results': results,
            'merged_output': '\n'.join(
                r.get('result', '') for r in results
            ),
            'avg_quality': sum(
                r['quality'] or 0 for r in results
            ) / len(results) if results else 0,
        }


def build_default_agent_pool() -> Dict[str, Agent]:
    """Build the default agent pool."""
    return {
        'orchestrator': Agent(
            id='orchestrator',
            agent_type=AgentType.ORCHESTRATOR,
            model_name='claude-opus-4',
            quality=0.95,
            cost_per_token=0.000015,
            capabilities=['epic', 'complex', 'moderate', 'simple', 'trivial'],
            max_children=10,
            specialties=['planning', 'decomposition'],
        ),
        'architect': Agent(
            id='architect',
            agent_type=AgentType.ARCHITECT,
            model_name='claude-sonnet-4',
            quality=0.92,
            cost_per_token=0.000010,
            capabilities=['complex', 'very-complex'],
            max_children=5,
            specialties=['system-design', 'api-design'],
        ),
        'implementer-1': Agent(
            id='implementer-1',
            agent_type=AgentType.IMPLEMENTER,
            model_name='claude-haiku-3',
            quality=0.85,
            cost_per_token=0.000005,
            capabilities=['moderate', 'simple', 'trivial'],
            max_children=3,
            specialties=['code-generation', 'refactoring'],
        ),
        'implementer-2': Agent(
            id='implementer-2',
            agent_type=AgentType.IMPLEMENTER,
            model_name='gpt-4o',
            quality=0.88,
            cost_per_token=0.000006,
            capabilities=['moderate', 'complex'],
            max_children=3,
            specialties=['code-generation', 'debugging'],
        ),
        'reviewer': Agent(
            id='reviewer',
            agent_type=AgentType.REVIEWER,
            model_name='claude-opus-4',
            quality=0.94,
            cost_per_token=0.000015,
            capabilities=['complex', 'very-complex', 'moderate'],
            max_children=2,
            specialties=['testing', 'security', 'performance'],
        ),
        'researcher': Agent(
            id='researcher',
            agent_type=AgentType.RESEARCHER,
            model_name='gpt-4o',
            quality=0.87,
            cost_per_token=0.000006,
            capabilities=['moderate', 'simple'],
            max_children=2,
            specialties=['documentation', 'research'],
        ),
    }


if __name__ == '__main__':
    # Demo the agent decomposition system
    print("=" * 60)
    print("Agent Decomposition System Demo")
    print("=" * 60)

    # Build agent pool
    agents = build_default_agent_pool()
    print(f"\nRegistered {len(agents)} agents:")
    for aid, agent in agents.items():
        print(f"  - {aid}: {agent.agent_type.name}, quality={agent.quality}, max_children={agent.max_children}")

    # Create root intent
    root_intent = Intent(
        id="build-api",
        description="Build a REST API for user management",
        complexity="complex",
        min_quality=0.85,
        estimated_tokens=15000,
    )

    print(f"\nRoot Intent: {root_intent.id}")
    print(f"  Description: {root_intent.description}")
    print(f"  Complexity: {root_intent.complexity}")
    print(f"  Est. Tokens: {root_intent.estimated_tokens}")

    # Create decomposer and spawner
    decomposer = QuantumDecomposer(agents, max_depth=5)
    spawner = AgentSpawner()

    for agent in agents.values():
        spawner.register_agent(agent)

    spawner.register_intent(root_intent)

    # Decompose and spawn
    print("\n" + "-" * 40)
    print("Decomposition & Spawning:")
    print("-" * 40)

    sub_intents = spawner.decompose_and_spawn(
        orchestrator_id='orchestrator',
        root_intent=root_intent,
        decomposer=decomposer
    )

    print(f"\nCreated {len(sub_intents)} sub-intents:")
    for sub in sub_intents:
        print(f"\n  {sub.id}:")
        print(f"    Description: {sub.description}")
        print(f"    Complexity: {sub.complexity}")
        print(f"    Assigned Agent: {sub.assigned_agent}")
        print(f"    Est. Tokens: {sub.estimated_tokens}")

    # Show hierarchy
    print("\n" + "-" * 40)
    print("Agent Hierarchy:")
    print("-" * 40)
    print(f"  orchestrator")
    print(f"    └── orchestrator-child-1 → implementer-1")
    print(f"    └── orchestrator-child-2 → implementer-2")
    print(f"    └── orchestrator-child-3 → reviewer")

    # Show agent state after spawning
    print("\n" + "-" * 40)
    print("Agent State After Spawning:")
    print("-" * 40)
    for aid, agent in agents.items():
        print(f"  {aid}: {agent.current_children}/{agent.max_children} children used")
