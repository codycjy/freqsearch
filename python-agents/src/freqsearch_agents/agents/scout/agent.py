"""Scout Agent - LangGraph definition.

The Scout Agent is responsible for discovering new trading strategies
from various data sources, validating them, and submitting unique
strategies for further processing.

Workflow:
1. Fetch strategies from configured sources (e.g., strat.ninja)
2. Parse and validate each strategy's code structure
3. Compute code hashes and deduplicate against existing strategies
4. Submit unique, valid strategies to the message queue
"""

from typing import Any

from langgraph.graph import END, StateGraph

import structlog

from ...core.state import ScoutState
from ...core.messaging import publish_event, Events
from .nodes import (
    fetch_strategies_node,
    validate_strategies_node,
    deduplicate_node,
    submit_strategies_node,
)

logger = structlog.get_logger(__name__)


def create_scout_agent() -> StateGraph:
    """Create the Scout Agent LangGraph.

    The Scout Agent follows a linear pipeline:
    fetch -> validate -> deduplicate -> submit

    Returns:
        Compiled LangGraph
    """
    # Create the workflow
    workflow = StateGraph(ScoutState)

    # Add nodes
    workflow.add_node("fetch", fetch_strategies_node)
    workflow.add_node("validate", validate_strategies_node)
    workflow.add_node("deduplicate", deduplicate_node)
    workflow.add_node("submit", submit_strategies_node)

    # Define edges (linear flow)
    workflow.set_entry_point("fetch")
    workflow.add_edge("fetch", "validate")
    workflow.add_edge("validate", "deduplicate")
    workflow.add_edge("deduplicate", "submit")
    workflow.add_edge("submit", END)

    return workflow.compile()


async def run_scout(
    source: str = "stratninja",
    limit: int = 50,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Run the Scout Agent to discover strategies.

    Args:
        source: Data source to use ("stratninja", "github", etc.)
        limit: Maximum number of strategies to fetch
        run_id: Optional run ID for tracking and progress reporting

    Returns:
        Final state with discovery results
    """
    logger.info(
        "Starting Scout Agent",
        source=source,
        limit=limit,
        run_id=run_id,
    )

    # Publish scout.started event
    if run_id:
        await publish_event(
            routing_key=Events.SCOUT_STARTED,
            body={
                "run_id": run_id,
                "source": source,
            },
        )

    try:
        # Create agent
        agent = create_scout_agent()

        # Initialize state
        initial_state: ScoutState = {
            "messages": [],
            "current_source": source,
            "raw_strategies": [],
            "validated_strategies": [],
            "unique_strategies": [],
            "total_fetched": 0,
            "validation_failed": 0,
            "duplicates_removed": 0,
            "submitted_count": 0,
            "errors": [],
        }

        # Add configuration with run_id
        config = {"configurable": {"limit": limit, "run_id": run_id}}

        # Run the agent
        final_state = await agent.ainvoke(initial_state, config=config)

        logger.info(
            "Scout Agent completed",
            total_fetched=final_state["total_fetched"],
            validation_failed=final_state["validation_failed"],
            duplicates_removed=final_state["duplicates_removed"],
            submitted=final_state["submitted_count"],
            run_id=run_id,
        )

        # Publish scout.completed event
        if run_id:
            await publish_event(
                routing_key=Events.SCOUT_COMPLETED,
                body={
                    "run_id": run_id,
                    "total_fetched": final_state["total_fetched"],
                    "validated": len(final_state["validated_strategies"]),
                    "validation_failed": final_state["validation_failed"],
                    "duplicates_removed": final_state["duplicates_removed"],
                    "submitted": final_state["submitted_count"],
                },
            )

        return final_state

    except Exception as e:
        logger.error("Scout Agent failed", error=str(e), run_id=run_id)

        # Publish scout.failed event
        if run_id:
            await publish_event(
                routing_key=Events.SCOUT_FAILED,
                body={
                    "run_id": run_id,
                    "error_message": str(e),
                },
            )

        raise
