#!/usr/bin/env python
"""Test script for code review functionality."""

import asyncio


async def test_code_review():
    """Test the code review functionality."""
    from src.freqsearch_agents.agents.analyst import run_analyst_code_review

    # Sample code to review
    code = """
from freqtrade.strategy import IStrategy
import talib.abstract as ta

class TestStrategy(IStrategy):
    def populate_indicators(self, dataframe, metadata):
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['ema20'] = ta.EMA(dataframe, timeperiod=20)
        return dataframe

    def populate_entry_trend(self, dataframe, metadata):
        dataframe.loc[
            (dataframe['rsi'] < 35) &  # Relaxed from <30
            (dataframe['close'] > dataframe['ema20']),  # Added trend filter
            'enter_long'
        ] = 1
        return dataframe
"""

    # Sample diagnosis
    diagnosis = {
        "suggestion_type": "MODIFY_CONDITION",
        "suggestion_description": "Relax RSI threshold and add trend filter",
        "issues": ["Too few trades", "Entry conditions too restrictive"],
    }

    # Sample baseline result
    baseline_result = {
        "total_trades": 5,
        "profit_pct": 2.5,
        "win_rate": 0.4,
        "sharpe_ratio": 0.3,
    }

    print("Testing code review functionality...")
    print("\nCode to review:")
    print("-" * 60)
    print(code)
    print("-" * 60)

    print("\nDiagnosis:")
    print(f"  Type: {diagnosis['suggestion_type']}")
    print(f"  Description: {diagnosis['suggestion_description']}")
    print(f"  Issues: {', '.join(diagnosis['issues'])}")

    print("\nBaseline Performance:")
    print(f"  Trades: {baseline_result['total_trades']}")
    print(f"  Profit: {baseline_result['profit_pct']}%")
    print(f"  Win Rate: {baseline_result['win_rate']*100:.1f}%")

    print("\nRunning code review...")
    try:
        result = await run_analyst_code_review(
            code=code,
            diagnosis=diagnosis,
            baseline_result=baseline_result,
        )

        print("\nReview Result:")
        print(f"  Approved: {result['approved']}")
        print(f"  Feedback: {result['feedback']}")
        if result['issues']:
            print(f"  Issues: {', '.join(result['issues'])}")
        else:
            print("  Issues: None")

        return result
    except Exception as e:
        print(f"\nError during review: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    result = asyncio.run(test_code_review())
    if result:
        print("\nTest completed successfully!")
        exit(0)
    else:
        print("\nTest failed!")
        exit(1)
