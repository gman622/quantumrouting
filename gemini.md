# Gemini Project Guide: Quantum Agent Annealed Swarm (QAAS)

This file provides guidance for working with the QAAS codebase.

## Project Overview

QAAS (Quantum Agent Annealed Swarm) is a proof-of-concept that uses quantum annealing and classical optimization to optimally assign tasks ("intents") to a heterogeneous swarm of AI agents. The current focus is on a **10,000-task CSS Renderer pipeline**, where the core problem is to find the assignment of N intents to M agents that minimizes total cost while satisfying constraints like agent capabilities, quality bars, capacity, **deadlines**, and **context affinity**.

## How to Run

The primary entry point for the 10k CSS Renderer simulation is the `notebooks/quantum-routing-10k.ipynb` notebook.

1.  **Activate the virtual environment:**
    ```bash
    source .venv/bin/activate
    ```
2.  **Install the project as an editable package:**
    ```bash
    pip install -e .
    ```
    This makes the `src/` modules importable.
3.  **Run the notebook:** Open `notebooks/quantum-routing-10k.ipynb` in a Jupyter environment and run its cells. The notebook is self-contained and includes output from a previous run.

## Project Architecture

The project is now organized into a standard structure:

*   **`notebooks/`**: Contains all Jupyter notebooks, including `quantum-routing-10k.ipynb` (the main simulation) and `decomposition-ide.ipynb` (for exploring task decomposition economics).
*   **`src/`**: Contains all Python source code modules. These modules are imported by the notebooks and include:
    *   `src/css_renderer_config.py`: Hyperparameters, token estimates, solver settings, and new cost weights (deadline, context affinity).
    *   `src/css_renderer_agents.py`: Defines the pool of 300 cloud and local agents, their costs, capacities, and capabilities.
    *   `src/css_renderer_intents.py`: Handles the generation of 10,000 CSS renderer tasks, their pipeline-stage dependency chains, and **deterministic deadlines**.
    *   `src/css_renderer_model.py`: Provides utility functions for problem size estimation.
    *   `src/solve_10k_ortools.py`: Implements the CP-SAT solver for the 10k problem, incorporating the enriched cost model.
    *   `src/report_10k.py`: Includes functions to print the final assignment reports and comparisons.
    *   `src/hybrid_router.py`: (New) An intelligent router that selects and orchestrates solvers based on problem characteristics.
*   **`docs/`**: Contains all markdown documentation files, including detailed specifications and charts.
*   **`pyproject.toml`**: Defines the project and makes the `src/` directory an installable Python package.

## Key Documentation

For deeper understanding of the project's theory and design, refer to the markdown files in the `docs/` directory.