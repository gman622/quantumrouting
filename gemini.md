# Gemini Project Guide: Quantum Agent Annealed Swarm (QAAS)

This file provides guidance for working with the QAAS codebase.

## Project Overview

QAAS (Quantum Agent Annealed Swarm) is a proof-of-concept that uses quantum annealing to optimally assign tasks ("intents") to a heterogeneous swarm of AI agents. The core problem is to find the assignment of N intents to M agents that minimizes total cost while satisfying constraints like agent capabilities, quality bars, and capacity.

## How to Run

The primary entry point is the `quantum-routing.ipynb` notebook.

1.  Activate the virtual environment:
    ```bash
    source .venv/bin/activate
    ```
2.  Run the cells in `quantum-routing.ipynb`. The notebook is self-contained and includes output from a previous run.

To run on a real D-Wave quantum computer, you will need a Leap API token and to uncomment the relevant cells in the notebook.

## Project Architecture

The project is orchestrated by `quantum-routing.ipynb`, which imports from the following Python modules:

*   **`config.py`**: Contains all hyperparameters, solver settings, and token estimations.
*   **`agents.py`**: Defines the pool of 48 cloud and local agents, their costs, capacities, and capabilities.
*   **`intents.py`**: Handles the generation of 1000 test intents and their dependency chains.
*   **`model.py`**: Implements the cost function (token cost, overkill, latency) and builds the Constrained Quadratic Model (CQM) for the D-Wave solver.
*   **`solve.py`**: Contains the logic for solving the CQM using simulated annealing (`solve_sa`), the D-Wave hybrid solver (`solve_hybrid`), and a `greedy_solve` baseline.
*   **`report.py`**: Includes functions to print the final assignment reports and comparisons between solvers.

## Key Documentation

For deeper understanding of the project's theory and design:

*   `quantum-agent-annealed-swarm.md`: The core QUBO formulation and cost model.
*   `dependency-aware-routing.md`: Algorithm for handling intent dependencies.
*   `mvrp-to-qaas-mapping.md`: Mapping from the agent routing problem to D-Wave's MVRP.
*   `nextsteps.md`: Project roadmap.
