# QAAS — Quantum Agent Annealed Swarm (10K CSS Renderer)

Quantum annealing and classical optimization to optimally assign **10,000 coding tasks** ("intents") to a heterogeneous swarm of **300 AI agents**. This project simulates the routing of tasks through a **CSS Renderer pipeline** (Parsing → Style Computation → Layout → Painting → Compositing).

Given N intents and M agents with different costs, quality levels, capabilities, and capacities, the goal is to find the assignment that minimizes total cost while satisfying all constraints, including:
*   **Token-based costs:** Realistic cost model based on estimated tokens and agent token rates.
*   **Deterministic deadlines:** Tasks have project-driven deadlines, with penalties for late completion.
*   **Context affinity:** Bonus for assigning dependent tasks to the same agent to reduce context switching overhead.
*   **Dependency chains:** Tasks within and across pipeline stages have dependencies.
*   **Agent capacity and quality bars.**

The problem is solved using Google's OR-Tools CP-SAT solver, which is well-suited for this scale.

## Project Structure

The project is organized as follows:

*   **`notebooks/`**: Contains Jupyter notebooks for simulations and analysis.
    *   `quantum-routing-10k.ipynb`: The main 10k CSS Renderer simulation.
    *   `decomposition-ide.ipynb`: Explores the economics of task decomposition.
*   **`src/`**: Contains all Python source code modules, structured as an installable package.
    *   `src/css_renderer_config.py`: Hyperparameters and cost model weights.
    *   `src/css_renderer_agents.py`: Agent pool definitions.
    *   `src/css_renderer_intents.py`: Intent generation and deadline assignment.
    *   `src/solve_10k_ortools.py`: CP-SAT solver implementation.
    *   `src/report_10k.py`: Reporting utilities.
    *   `src/hybrid_router.py`: Intelligent solver selection and orchestration.
*   **`docs/`**: Contains all project documentation and specifications.
*   **`pyproject.toml`**: Project metadata and build configuration.
*   `.venv/`: Python virtual environment.

## Agent Pool (300 Agents)

The agent pool consists of 240 cloud agents (Claude, GPT-5.2, Gemini, Kimi-2.5) and 60 local agents (Llama, Mistral, etc.).

| Type | Models | Sessions | Capacity/session | Total slots |
|------|--------|----------|------------------|-------------|
| Cloud | claude, gpt5.2, gemini, kimi2.5 | 60 each | 50 | 12,000 |
| Local | llama, mistral, codellama, qwen2 | 10 each | 6–10 | 420 |
| **Total** | **10 models** | **300 agents** | | **12,420** |

## Intent Backlog (10,000 Intents)

Tasks are distributed across 5 CSS pipeline stages and 6 complexity tiers.

| Tier | Count | Tokens/intent | SP/intent | Total tokens | Total SP |
|------|-------|---------------|-----------|-------------|----------|
| trivial | 1,925 | 500 | 1 | 962,500 | 1,925 |
| simple | 2,825 | 1,500 | 2 | 4,237,500 | 5,650 |
| moderate | 2,875 | 5,000 | 3 | 14,375,000 | 8,625 |
| complex | 1,675 | 12,000 | 5 | 20,100,000 | 8,375 |
| very-complex | 600 | 25,000 | 8 | 15,000,000 | 4,800 |
| epic | 100 | 60,000 | 13 | 6,000,000 | 1,300 |
| **Total** | **10,000** | | | **60,675,000** | **30,675** |

Workflow chains (630 total) create intra-stage and cross-stage dependencies, forcing sequential execution within pipelines.

## Running the Simulation

1.  **Activate your Python virtual environment:**
    ```bash
    source .venv/bin/activate
    ```
2.  **Install the project's source code:**
    ```bash
    pip install -e .
    ```
    This makes the `src/` modules importable by the notebooks.
3.  **Open the main notebook:** Launch Jupyter and open `notebooks/quantum-routing-10k.ipynb`.
4.  **Run all cells:** Execute the cells sequentially to run the 10k CSS Renderer simulation.

## Dependencies

The project primarily uses:
*   `ortools` (Google OR-Tools CP-SAT solver)
*   `numpy`
*   `matplotlib`
*   `dwave-ocean-sdk` (for potential D-Wave hybrid solver integration, though CP-SAT is currently used for 10k scale)

Python 3.13 is recommended.

## Next Steps

Refer to `docs/nextsteps.md` for the project roadmap, including scaling to 100k/1M tasks, integrating D-Wave hybrid solvers, and implementing recursive task decomposition.