"""Scout Agent node implementations.

Each node is an async function that takes state and returns partial state updates.
"""

from typing import Any

import structlog

from ...core.state import ScoutState
from ...core.messaging import publish_event, Events
from ...tools.sources.stratninja import StratNinjaSource
from ...tools.code.parser import FreqtradeCodeParser
from ...tools.code.simhash import compute_code_hash, deduplicate_strategies
from ...schemas.strategy import RawStrategy, StrategySource

logger = structlog.get_logger(__name__)


async def fetch_strategies_node(
    state: ScoutState,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fetch strategies from the configured data source.

    Args:
        state: Current agent state
        config: Optional configuration (contains limit and run_id)

    Returns:
        State update with raw_strategies
    """
    source_name = state["current_source"]
    limit = 50
    run_id = None

    if config and "configurable" in config:
        limit = config["configurable"].get("limit", 50)
        run_id = config["configurable"].get("run_id")

    logger.info("Fetching strategies", source=source_name, limit=limit, run_id=run_id)

    # Publish progress: starting fetch
    if run_id:
        await publish_event(
            routing_key=Events.SCOUT_PROGRESS,
            body={
                "run_id": run_id,
                "stage": "fetch",
                "progress": 0,
                "message": f"Starting strategy fetch from {source_name}",
            },
        )

    # Select source implementation
    if source_name == "stratninja":
        source = StratNinjaSource()
    else:
        return {
            "errors": state["errors"] + [f"Unknown source: {source_name}"],
            "total_fetched": 0,
        }

    try:
        # Fetch strategy list and code
        strategies = await source.fetch_strategies(limit=limit)

        # Convert to dictionaries for state
        raw_strategies = []
        for s in strategies:
            # Compute code hash
            code_hash = compute_code_hash(s.code) if s.code else ""

            raw_strategies.append({
                "name": s.name,
                "source": s.source,
                "source_url": s.source_url,
                "code": s.code,
                "code_hash": code_hash,
                "timeframe": s.timeframe,
                "stoploss": s.stoploss,
                "description": s.description,
            })

        logger.info("Fetched strategies", count=len(raw_strategies))

        # Publish progress: fetch complete (25%)
        if run_id:
            await publish_event(
                routing_key=Events.SCOUT_PROGRESS,
                body={
                    "run_id": run_id,
                    "stage": "fetch",
                    "progress": 25,
                    "message": f"Fetched {len(raw_strategies)} strategies",
                    "stage_metrics": {"total_fetched": len(raw_strategies)},
                },
            )

        return {
            "raw_strategies": raw_strategies,
            "total_fetched": len(raw_strategies),
        }

    except Exception as e:
        logger.error("Failed to fetch strategies", error=str(e))
        return {
            "errors": state["errors"] + [f"Fetch error: {str(e)}"],
            "total_fetched": 0,
        }


async def validate_strategies_node(
    state: ScoutState,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate strategy code structure.

    Checks each strategy for:
    - Valid Python syntax
    - IStrategy class definition
    - Required methods (populate_indicators, populate_entry/buy_trend, etc.)

    Args:
        state: Current agent state
        config: Optional configuration (contains run_id)

    Returns:
        State update with validated_strategies
    """
    run_id = None
    if config and "configurable" in config:
        run_id = config["configurable"].get("run_id")

    # Publish progress: starting validation
    if run_id:
        await publish_event(
            routing_key=Events.SCOUT_PROGRESS,
            body={
                "run_id": run_id,
                "stage": "validate",
                "progress": 25,
                "message": f"Starting validation of {len(state['raw_strategies'])} strategies",
            },
        )

    parser = FreqtradeCodeParser()
    validated = []
    failed_count = 0
    failed_strategies = []  # Track failed strategies for detailed logging

    for strategy in state["raw_strategies"]:
        strategy_name = strategy.get("name", "unknown")
        code = strategy.get("code", "")

        if not code:
            failed_count += 1
            failed_strategies.append({
                "name": strategy_name,
                "reason": "empty_code",
                "error": "No code content",
            })
            continue

        result = parser.parse(code, strategy_name=strategy_name)

        if result.is_valid and result.is_strategy:
            # Check if required methods are present
            if not result.required_methods_missing:
                strategy["parse_result"] = {
                    "class_name": result.class_name,
                    "indicators": result.indicators_used,
                    "parameters": result.parameters,
                    "uses_deprecated_api": result.uses_deprecated_api,
                    "timeframe": result.timeframe or strategy.get("timeframe"),
                    "stoploss": result.stoploss or strategy.get("stoploss"),
                }
                # Update detected info
                strategy["detected_indicators"] = result.indicators_used
                if result.timeframe:
                    strategy["timeframe"] = result.timeframe
                if result.stoploss:
                    strategy["stoploss"] = result.stoploss

                validated.append(strategy)
                logger.debug("Strategy validated successfully", name=strategy_name)
            else:
                logger.warning(
                    "Strategy missing required methods",
                    name=strategy_name,
                    missing=result.required_methods_missing,
                    methods_found=result.methods[:5],  # First 5 methods for context
                )
                failed_count += 1
                failed_strategies.append({
                    "name": strategy_name,
                    "reason": "missing_methods",
                    "error": f"Missing: {', '.join(result.required_methods_missing)}",
                })
        else:
            if result.syntax_error:
                logger.warning(
                    "Strategy has syntax error",
                    name=strategy_name,
                    error=result.syntax_error,
                )
                failed_strategies.append({
                    "name": strategy_name,
                    "reason": "syntax_error",
                    "error": result.syntax_error,
                })
            elif not result.is_strategy:
                logger.warning(
                    "No IStrategy class found",
                    name=strategy_name,
                )
                failed_strategies.append({
                    "name": strategy_name,
                    "reason": "no_istrategy",
                    "error": "No class extending IStrategy found",
                })
            failed_count += 1

    # Log summary of failures
    if failed_strategies:
        logger.info(
            "Validation failures summary",
            total_failed=len(failed_strategies),
            by_reason={
                reason: len([f for f in failed_strategies if f["reason"] == reason])
                for reason in set(f["reason"] for f in failed_strategies)
            },
        )

    logger.info(
        "Validation complete",
        valid=len(validated),
        failed=failed_count,
    )

    # Publish progress: validation complete (50%)
    if run_id:
        await publish_event(
            routing_key=Events.SCOUT_PROGRESS,
            body={
                "run_id": run_id,
                "stage": "validate",
                "progress": 50,
                "message": f"Validated {len(validated)} strategies, {failed_count} failed",
                "stage_metrics": {
                    "validated": len(validated),
                    "validation_failed": failed_count,
                },
            },
        )

    return {
        "validated_strategies": validated,
        "validation_failed": failed_count,
    }


async def deduplicate_node(
    state: ScoutState,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Remove duplicate strategies using SimHash.

    Compares code hashes to identify near-duplicate strategies.
    Also checks against existing strategies in the database.

    Args:
        state: Current agent state
        config: Optional configuration (contains run_id)

    Returns:
        State update with unique_strategies
    """
    run_id = None
    if config and "configurable" in config:
        run_id = config["configurable"].get("run_id")

    # Publish progress: starting deduplication
    if run_id:
        await publish_event(
            routing_key=Events.SCOUT_PROGRESS,
            body={
                "run_id": run_id,
                "stage": "deduplicate",
                "progress": 50,
                "message": f"Starting deduplication of {len(state['validated_strategies'])} strategies",
            },
        )

    strategies = state["validated_strategies"]

    if not strategies:
        return {
            "unique_strategies": [],
            "duplicates_removed": 0,
        }

    # TODO: Fetch existing hashes from database via gRPC
    # For now, just deduplicate within the current batch
    existing_hashes: list[str] = []

    # Deduplicate within batch
    unique, duplicates = deduplicate_strategies(
        strategies,
        hash_field="code_hash",
        id_field="name",
        threshold=3,
    )

    # Filter out strategies that match existing ones
    # (This will be implemented when gRPC client is ready)
    final_unique = []
    for strategy in unique:
        code_hash = strategy.get("code_hash", "")
        # Skip if hash matches existing
        # For now, accept all
        final_unique.append(strategy)

    logger.info(
        "Deduplication complete",
        unique=len(final_unique),
        duplicates=len(duplicates),
    )

    # Publish progress: deduplication complete (75%)
    if run_id:
        await publish_event(
            routing_key=Events.SCOUT_PROGRESS,
            body={
                "run_id": run_id,
                "stage": "deduplicate",
                "progress": 75,
                "message": f"Found {len(final_unique)} unique strategies, removed {len(strategies) - len(final_unique)} duplicates",
                "stage_metrics": {
                    "unique": len(final_unique),
                    "duplicates_removed": len(strategies) - len(final_unique),
                },
            },
        )

    return {
        "unique_strategies": final_unique,
        "duplicates_removed": len(strategies) - len(final_unique),
    }


async def submit_strategies_node(
    state: ScoutState,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Submit unique strategies to the message queue.

    Publishes strategy.discovered events for each unique strategy.

    Args:
        state: Current agent state
        config: Optional configuration (contains run_id)

    Returns:
        State update with submitted_count
    """
    run_id = None
    if config and "configurable" in config:
        run_id = config["configurable"].get("run_id")

    # Publish progress: starting submission
    if run_id:
        await publish_event(
            routing_key=Events.SCOUT_PROGRESS,
            body={
                "run_id": run_id,
                "stage": "submit",
                "progress": 75,
                "message": f"Starting submission of {len(state['unique_strategies'])} strategies",
            },
        )

    strategies = state["unique_strategies"]
    submitted = 0
    errors = []

    for strategy in strategies:
        try:
            # Prepare event payload
            event_data = {
                "name": strategy.get("name", ""),
                "source_type": strategy.get("source", "unknown"),
                "source_url": strategy.get("source_url", ""),
                "code": strategy.get("code", ""),
                "code_hash": strategy.get("code_hash", ""),
                "detected_indicators": strategy.get("detected_indicators", []),
                "timeframe": strategy.get("timeframe"),
                "stoploss": strategy.get("stoploss"),
                "is_valid": True,
                "validation_errors": [],
            }

            # Publish to message queue
            await publish_event(
                routing_key=Events.STRATEGY_DISCOVERED,
                body=event_data,
            )

            submitted += 1
            logger.debug("Submitted strategy", name=strategy.get("name"))

        except Exception as e:
            error_msg = f"Failed to submit {strategy.get('name')}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

    logger.info("Submission complete", submitted=submitted, errors=len(errors))

    # Publish progress: submission complete (100%)
    if run_id:
        await publish_event(
            routing_key=Events.SCOUT_PROGRESS,
            body={
                "run_id": run_id,
                "stage": "submit",
                "progress": 100,
                "message": f"Submitted {submitted} strategies",
                "stage_metrics": {
                    "submitted": submitted,
                    "errors": len(errors),
                },
            },
        )

    return {
        "submitted_count": submitted,
        "errors": state["errors"] + errors,
    }
