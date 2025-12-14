"""Prompt templates for Analyst Agent."""


def get_analysis_prompt(
    strategy_name: str,
    metrics: dict,
    trade_context: str,
    issues: list[str],
) -> str:
    """Generate the analysis prompt."""

    existing_issues = "\n".join(f"- {i}" for i in issues) if issues else "None detected"

    return f"""Analyze this backtest result for strategy "{strategy_name}":

## Performance Metrics
- Total Trades: {metrics.get('total_trades', 'N/A')}
- Win Rate: {metrics.get('win_rate', 0):.1%}
- Total Profit: {metrics.get('profit_pct', 0):.2%}
- Max Drawdown: {metrics.get('max_drawdown_pct', 0):.2%}
- Sharpe Ratio: {metrics.get('sharpe_ratio', 'N/A')}
- Profit Factor: {metrics.get('profit_factor', 'N/A')}
- Calmar Ratio: {metrics.get('calmar_ratio', 'N/A')}
- Expectancy: {metrics.get('expectancy', 'N/A')}
- Average Trade Duration: {metrics.get('avg_trade_duration_minutes', 'N/A')} minutes
- Best Trade: {metrics.get('best_trade_pct', 'N/A')}%
- Worst Trade: {metrics.get('worst_trade_pct', 'N/A')}%

## Trade Analysis
{trade_context}

## Already Identified Issues
{existing_issues}

## Decision Criteria
READY_FOR_LIVE if:
- Win rate > 40% AND profit > 10% AND max drawdown < 30%
- OR Sharpe ratio > 1.5 AND profit > 5%
- High confidence in sustainability

NEEDS_MODIFICATION if:
- Strategy shows potential but has fixable issues
- Specific improvements can be identified
- Not ready for live but worth iterating

ARCHIVE if:
- Fundamental flaws in approach
- Negative expectancy with no clear fix
- Too few trades or unreliable signals

## Your Task
1. Identify additional issues not already listed
2. Determine root causes for the issues
3. Make a decision (READY_FOR_LIVE, NEEDS_MODIFICATION, or ARCHIVE)
4. If NEEDS_MODIFICATION, provide specific suggestion_type and description
5. Rate your confidence in this decision (0.0 to 1.0)

Respond with JSON in the specified format."""


def get_detailed_trade_analysis_prompt(
    losing_trades: list[dict],
    market_data: dict | None = None,
) -> str:
    """Generate prompt for detailed losing trade analysis."""

    trades_summary = []
    for i, trade in enumerate(losing_trades[:10]):  # Limit to 10
        trades_summary.append(
            f"{i+1}. {trade.get('pair', 'N/A')}: "
            f"Loss {trade.get('profit_ratio', 0):.2%}, "
            f"Duration {trade.get('trade_duration_minutes', 'N/A')} min"
        )

    trades_text = "\n".join(trades_summary)

    return f"""Analyze these losing trades to identify patterns:

## Losing Trades
{trades_text}

## Questions to Answer
1. Are losses concentrated in specific pairs?
2. Is there a pattern in trade duration (too short/long)?
3. Were entries made in unfavorable market conditions?
4. Could a simple filter have prevented these losses?

Provide insights that can help improve the strategy."""
