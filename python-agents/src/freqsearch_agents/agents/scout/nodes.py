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
        config: Optional configuration (contains limit)

    Returns:
        State update with raw_strategies
    """
    source_name = state["current_source"]
    limit = 50

    if config and "configurable" in config:
        limit = config["configurable"].get("limit", 50)

    logger.info("Fetching strategies", source=source_name, limit=limit)

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
        config: Optional configuration

    Returns:
        State update with validated_strategies
    """
    parser = FreqtradeCodeParser()
    validated = []
    failed_count = 0

    for strategy in state["raw_strategies"]:
        code = strategy.get("code", "")
        if not code:
            failed_count += 1
            continue

        result = parser.parse(code)

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
            else:
                logger.debug(
                    "Strategy missing required methods",
                    name=strategy.get("name"),
                    missing=result.required_methods_missing,
                )
                failed_count += 1
        else:
            logger.debug(
                "Strategy validation failed",
                name=strategy.get("name"),
                error=result.syntax_error,
                is_strategy=result.is_strategy,
            )
            failed_count += 1

    logger.info(
        "Validation complete",
        valid=len(validated),
        failed=failed_count,
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
        config: Optional configuration

    Returns:
        State update with unique_strategies
    """
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
        config: Optional configuration

    Returns:
        State update with submitted_count
    """
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

    return {
        "submitted_count": submitted,
        "errors": state["errors"] + errors,
    }
