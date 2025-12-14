"""Analyst Agent node implementations."""

import math
from typing import Any

import structlog

from ...core.state import AnalystState
from ...core.llm import get_llm
from ...core.messaging import publish_event, Events
from ...schemas.diagnosis import (
    DiagnosisReport,
    DiagnosisStatus,
    SuggestionType,
    MetricsSummary,
)
from .prompts import get_analysis_prompt

logger = structlog.get_logger(__name__)


async def compute_metrics_node(
    state: AnalystState,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute advanced performance metrics.

    Calculates metrics beyond what the backtest provides:
    - Sharpe Ratio (if not provided)
    - Sortino Ratio
    - Calmar Ratio
    - Expectancy
    - Max Drawdown Duration

    Args:
        state: Current agent state
        config: Optional configuration

    Returns:
        State update with computed metrics
    """
    result = state["backtest_result"]

    # Extract basic metrics from result
    metrics = {
        "total_trades": result.get("total_trades", 0),
        "winning_trades": result.get("winning_trades", 0),
        "losing_trades": result.get("losing_trades", 0),
        "profit_total": result.get("profit_total", 0.0),
        "profit_pct": result.get("profit_pct", 0.0),
        "max_drawdown": result.get("max_drawdown", 0.0),
        "max_drawdown_pct": result.get("max_drawdown_pct", 0.0),
    }

    # Calculate win rate
    total = metrics["total_trades"]
    if total > 0:
        metrics["win_rate"] = metrics["winning_trades"] / total
    else:
        metrics["win_rate"] = 0.0

    # Get or calculate ratios
    metrics["sharpe_ratio"] = result.get("sharpe_ratio")
    metrics["sortino_ratio"] = result.get("sortino_ratio")
    metrics["calmar_ratio"] = result.get("calmar_ratio")
    metrics["profit_factor"] = result.get("profit_factor")

    # Calculate expectancy if we have trade details
    avg_win = result.get("avg_profit_winning", 0)
    avg_loss = result.get("avg_profit_losing", 0)
    win_rate = metrics["win_rate"]

    if avg_win and avg_loss and win_rate:
        # Expectancy = (Win% * Avg Win) - (Loss% * Avg Loss)
        metrics["expectancy"] = (win_rate * avg_win) - ((1 - win_rate) * abs(avg_loss))
    else:
        metrics["expectancy"] = None

    # Calculate Calmar Ratio if not provided
    if metrics["calmar_ratio"] is None and metrics["max_drawdown_pct"]:
        annual_return = metrics["profit_pct"]  # Simplified
        max_dd = abs(metrics["max_drawdown_pct"])
        if max_dd > 0:
            metrics["calmar_ratio"] = annual_return / max_dd

    # Trade duration stats
    metrics["avg_trade_duration_minutes"] = result.get("avg_trade_duration_minutes")
    metrics["best_trade_pct"] = result.get("best_trade_pct")
    metrics["worst_trade_pct"] = result.get("worst_trade_pct")
    metrics["avg_profit_per_trade"] = result.get("avg_profit_per_trade")

    logger.info(
        "Computed metrics",
        win_rate=metrics["win_rate"],
        profit_pct=metrics["profit_pct"],
        sharpe=metrics["sharpe_ratio"],
    )

    return {"metrics": metrics}


async def analyze_trades_node(
    state: AnalystState,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Analyze individual trades for patterns.

    Examines winning and losing trades to identify:
    - Common patterns in losing trades
    - Market conditions during losses
    - Trade clustering

    Args:
        state: Current agent state
        config: Optional configuration

    Returns:
        State update with trade analysis
    """
    result = state["backtest_result"]

    # Get trade list if available
    trades = result.get("trades", [])

    winning_trades = []
    losing_trades = []

    for trade in trades:
        profit = trade.get("profit_ratio", trade.get("profit_pct", 0))
        if profit >= 0:
            winning_trades.append(trade)
        else:
            losing_trades.append(trade)

    # Generate trade context summary
    trade_context = _generate_trade_context(winning_trades, losing_trades)

    return {
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "trade_context": trade_context,
    }


def _generate_trade_context(
    winning_trades: list[dict],
    losing_trades: list[dict],
) -> str:
    """Generate a text summary of trade patterns."""
    context_parts = []

    if winning_trades:
        avg_win = sum(t.get("profit_ratio", 0) for t in winning_trades) / len(winning_trades)
        context_parts.append(
            f"Winning trades ({len(winning_trades)}): Average profit {avg_win:.2%}"
        )

        # Analyze duration
        durations = [t.get("trade_duration_minutes", 0) for t in winning_trades]
        if durations:
            avg_duration = sum(durations) / len(durations)
            context_parts.append(f"  Average duration: {avg_duration:.0f} minutes")

    if losing_trades:
        avg_loss = sum(t.get("profit_ratio", 0) for t in losing_trades) / len(losing_trades)
        context_parts.append(
            f"Losing trades ({len(losing_trades)}): Average loss {avg_loss:.2%}"
        )

        # Analyze pairs with most losses
        pair_losses = {}
        for trade in losing_trades:
            pair = trade.get("pair", "unknown")
            pair_losses[pair] = pair_losses.get(pair, 0) + 1

        if pair_losses:
            worst_pair = max(pair_losses.items(), key=lambda x: x[1])
            context_parts.append(
                f"  Pair with most losses: {worst_pair[0]} ({worst_pair[1]} trades)"
            )

    return "\n".join(context_parts) if context_parts else "No trade details available"


async def generate_diagnosis_node(
    state: AnalystState,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate diagnosis using LLM.

    Analyzes metrics and trade patterns to:
    - Identify issues
    - Determine root causes
    - Make a decision (approve/modify/archive)
    - Generate specific suggestions if modification needed

    Args:
        state: Current agent state
        config: Optional configuration

    Returns:
        State update with diagnosis
    """
    metrics = state["metrics"]
    trade_context = state["trade_context"]
    result = state["backtest_result"]

    # Quick checks for obvious decisions
    issues = []
    root_causes = []

    # Check minimum requirements
    if metrics["total_trades"] < 10:
        issues.append("Insufficient trades for meaningful analysis")
        return {
            "issues": issues,
            "decision": DiagnosisStatus.ARCHIVE.value,
            "confidence": 0.9,
            "suggestion_type": None,
            "suggestion_description": "Strategy produces too few trades to analyze.",
        }

    # Check for severe issues
    if metrics["max_drawdown_pct"] and abs(metrics["max_drawdown_pct"]) > 50:
        issues.append("Excessive drawdown (>50%)")
        root_causes.append("Risk management may be inadequate")

    if metrics["win_rate"] < 0.3:
        issues.append("Low win rate (<30%)")

    if metrics["profit_pct"] < 0:
        issues.append("Negative total profit")

    # Use LLM for detailed analysis
    llm = get_llm()
    prompt = get_analysis_prompt(
        strategy_name=result.get("strategy_name", "unknown"),
        metrics=metrics,
        trade_context=trade_context,
        issues=issues,
    )

    messages = [
        {
            "role": "system",
            "content": """You are a quantitative trading analyst. Analyze strategy performance and make recommendations.
Output your analysis as JSON with the following structure:
{
    "decision": "READY_FOR_LIVE" | "NEEDS_MODIFICATION" | "ARCHIVE",
    "confidence": 0.0-1.0,
    "issues": ["issue1", "issue2"],
    "root_causes": ["cause1", "cause2"],
    "suggestion_type": "ADD_FILTER" | "ADD_STOPLOSS" | "MODIFY_CONDITION" | null,
    "suggestion_description": "Specific description of what to change",
    "target_metrics": ["metric1", "metric2"]
}""",
        },
        {"role": "user", "content": prompt},
    ]

    response = await llm.ainvoke(messages)

    # Parse LLM response
    diagnosis = _parse_diagnosis_response(response.content, issues, root_causes)

    logger.info(
        "Generated diagnosis",
        decision=diagnosis["decision"],
        confidence=diagnosis["confidence"],
        issues=diagnosis["issues"],
    )

    return diagnosis


def _parse_diagnosis_response(
    response: str,
    existing_issues: list[str],
    existing_causes: list[str],
) -> dict[str, Any]:
    """Parse LLM diagnosis response."""
    import json
    import re

    # Try to extract JSON
    json_match = re.search(r"\{[\s\S]*\}", response)
    if json_match:
        try:
            data = json.loads(json_match.group())

            decision = data.get("decision", "ARCHIVE")
            # Normalize decision
            if decision not in [s.value for s in DiagnosisStatus]:
                decision = DiagnosisStatus.ARCHIVE.value

            return {
                "decision": decision,
                "confidence": min(max(data.get("confidence", 0.5), 0.0), 1.0),
                "issues": existing_issues + data.get("issues", []),
                "root_causes": existing_causes + data.get("root_causes", []),
                "suggestion_type": data.get("suggestion_type"),
                "suggestion_description": data.get("suggestion_description"),
                "target_metrics": data.get("target_metrics", []),
            }
        except json.JSONDecodeError:
            pass

    # Fallback to rule-based decision
    return {
        "decision": DiagnosisStatus.NEEDS_MODIFICATION.value,
        "confidence": 0.5,
        "issues": existing_issues,
        "root_causes": existing_causes,
        "suggestion_type": "ADD_FILTER",
        "suggestion_description": "Consider adding trend filters to reduce drawdown",
        "target_metrics": ["max_drawdown_pct", "win_rate"],
    }


async def submit_decision_node(
    state: AnalystState,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Submit the diagnosis decision.

    Publishes appropriate event based on decision:
    - READY_FOR_LIVE: strategy.approved
    - NEEDS_MODIFICATION: strategy.evolve
    - ARCHIVE: strategy.archived

    Also enforces iteration limits: if max_iterations reached and decision
    would be NEEDS_MODIFICATION, force ARCHIVE instead to prevent infinite loops.

    Args:
        state: Current agent state
        config: Optional configuration

    Returns:
        State update with termination_reason if iteration limit reached
    """
    decision = state["decision"]
    result = state["backtest_result"]
    metrics = state["metrics"]
    termination_reason = None

    # Enforce iteration limit
    current_iteration = state.get("current_iteration", 0)
    max_iterations = state.get("max_iterations", 10)  # Default: 10 iterations

    if current_iteration >= max_iterations and decision == DiagnosisStatus.NEEDS_MODIFICATION.value:
        # Force archive when iteration limit reached
        decision = DiagnosisStatus.ARCHIVE.value
        termination_reason = f"Max iterations ({max_iterations}) reached without meeting criteria"
        logger.warning(
            "Iteration limit reached, forcing archive",
            current_iteration=current_iteration,
            max_iterations=max_iterations,
            strategy=result.get("strategy_name"),
        )

    if decision == DiagnosisStatus.READY_FOR_LIVE.value:
        # Determine market regime based on performance characteristics
        market_regime = _determine_market_regime(metrics, state.get("trade_context", ""))

        # Generate enhanced description with performance summary
        enhanced_description = _generate_enhanced_description(
            result.get("strategy_name", ""),
            metrics,
            market_regime,
        )

        # Publish approval event
        event_data = {
            "strategy_id": state["strategy_id"],
            "strategy_name": result.get("strategy_name", ""),
            "profit_pct": metrics.get("profit_pct", 0),
            "win_rate": metrics.get("win_rate", 0),
            "max_drawdown_pct": metrics.get("max_drawdown_pct", 0),
            "sharpe_ratio": metrics.get("sharpe_ratio"),
            "enhanced_description": enhanced_description,
            "market_regime": market_regime,
            "confidence": state["confidence"],
        }
        await publish_event(Events.STRATEGY_APPROVED, event_data)

    elif decision == DiagnosisStatus.NEEDS_MODIFICATION.value:
        # Publish evolve event
        event_data = {
            "strategy_id": state["strategy_id"],
            "strategy_name": result.get("strategy_name", ""),
            "current_code": result.get("strategy_code", ""),
            "diagnosis_job_id": state["job_id"],
            "suggestion_type": state["suggestion_type"] or "ADD_FILTER",
            "suggestion_description": state["suggestion_description"] or "",
            "target_metrics": state["target_metrics"],
            "previous_metrics": {
                "profit_pct": metrics.get("profit_pct", 0),
                "win_rate": metrics.get("win_rate", 0),
                "max_drawdown_pct": metrics.get("max_drawdown_pct", 0),
            },
        }
        await publish_event(Events.STRATEGY_EVOLVE, event_data)

    else:
        # Publish archive event
        event_data = {
            "strategy_id": state["strategy_id"],
            "strategy_name": result.get("strategy_name", ""),
            "reason": "; ".join(state["issues"]) if state["issues"] else "Poor performance",
            "final_metrics": {
                "profit_pct": metrics.get("profit_pct", 0),
                "win_rate": metrics.get("win_rate", 0),
                "max_drawdown_pct": metrics.get("max_drawdown_pct", 0),
            },
        }
        await publish_event(Events.STRATEGY_ARCHIVED, event_data)

    logger.info(
        "Submitted diagnosis decision",
        decision=decision,
        strategy=result.get("strategy_name"),
        iteration=current_iteration,
    )

    # Return termination_reason if set (iteration limit reached)
    if termination_reason:
        return {"termination_reason": termination_reason}

    return {}


def _determine_market_regime(metrics: dict[str, Any], trade_context: str) -> list[str]:
    """Determine suitable market regimes based on performance characteristics.

    Analyzes metrics to classify which market conditions the strategy performs best in:
    - trending: Works well in directional markets
    - ranging: Works well in sideways/consolidating markets
    - volatile: Can handle high volatility conditions

    Args:
        metrics: Computed performance metrics
        trade_context: Trade analysis context string

    Returns:
        List of market regime tags
    """
    regimes = []

    # High win rate + positive expectancy suggests trend-following works
    win_rate = metrics.get("win_rate", 0)
    profit_factor = metrics.get("profit_factor")
    max_drawdown = abs(metrics.get("max_drawdown_pct", 0))
    sharpe = metrics.get("sharpe_ratio")

    # Trending market indicator: consistent profits with moderate win rate
    if win_rate >= 0.4 and (profit_factor is None or profit_factor > 1.5):
        regimes.append("trending")

    # Ranging market indicator: high win rate with quick trades
    avg_duration = metrics.get("avg_trade_duration_minutes")
    if win_rate >= 0.55 and (avg_duration is None or avg_duration < 120):
        regimes.append("ranging")

    # Volatile market indicator: handles drawdown well with positive returns
    profit_pct = metrics.get("profit_pct", 0)
    if max_drawdown < 25 and profit_pct > 10:
        regimes.append("volatile")

    # Default to trending if no specific regime identified
    if not regimes:
        regimes.append("trending")

    return regimes


def _generate_enhanced_description(
    strategy_name: str,
    metrics: dict[str, Any],
    market_regime: list[str],
) -> str:
    """Generate enhanced description with performance summary.

    Creates a description that combines the strategy's behavior with its
    actual backtest performance results.

    Args:
        strategy_name: Name of the strategy
        metrics: Computed performance metrics
        market_regime: List of suitable market regimes

    Returns:
        Enhanced description string
    """
    profit_pct = metrics.get("profit_pct", 0)
    win_rate = metrics.get("win_rate", 0) * 100
    max_drawdown = abs(metrics.get("max_drawdown_pct", 0))
    sharpe = metrics.get("sharpe_ratio")
    total_trades = metrics.get("total_trades", 0)

    # Build performance summary
    parts = [
        f"Backtested with {total_trades} trades,",
        f"achieving {profit_pct:.1f}% return",
        f"with {win_rate:.1f}% win rate",
        f"and {max_drawdown:.1f}% max drawdown.",
    ]

    if sharpe is not None:
        parts.append(f"Sharpe ratio: {sharpe:.2f}.")

    # Add market regime suitability
    regime_str = ", ".join(market_regime)
    parts.append(f"Best suited for {regime_str} market conditions.")

    return " ".join(parts)
