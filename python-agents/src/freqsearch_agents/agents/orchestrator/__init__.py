"""Orchestrator Agent - Coordinates optimization loops.

The Orchestrator Agent manages the full optimization workflow:
1. Engineer → generates/evolves strategy code
2. Submit Backtest → sends to Go backend via gRPC
3. Wait for Result → polls until backtest completes
4. Analyst → analyzes results, makes decision
5. Decision routing:
   - APPROVE → end loop, mark optimization complete
   - MODIFY → send feedback to Engineer, iterate
   - ARCHIVE → discard strategy, try alternative
6. Iteration limit → if max_iterations reached, select best result
"""

from .agent import create_orchestrator_agent, run_orchestrator

__all__ = ["create_orchestrator_agent", "run_orchestrator"]
