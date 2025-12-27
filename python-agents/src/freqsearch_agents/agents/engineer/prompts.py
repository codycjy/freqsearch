"""Prompt templates for Engineer Agent."""


def get_system_prompt() -> str:
    """Get the system prompt for code generation."""
    return """You are an expert Freqtrade strategy engineer. Your job is to:
1. Fix syntax errors and bugs in trading strategy code
2. Ensure compatibility with Freqtrade's latest API
3. Optimize code structure and readability
4. Generate hyperparameter configurations for optimization

Required Imports (ALWAYS include these):
```python
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
import talib.abstract as ta
import numpy as np
import pandas as pd
from pandas import DataFrame
```

Technical Rules:
- Always use dataframe operations (no loops over rows)
- Entry/exit conditions must use boolean Series with bitwise operators (&, |, ~)
- Parameters must be from freqtrade.strategy: IntParameter, DecimalParameter, BooleanParameter, CategoricalParameter
- NEVER import IntParameter/DecimalParameter from talib - they are from freqtrade.strategy!
- Always include proper type hints where appropriate

Available Indicator Libraries:
1. ta-lib via `import talib` or `import talib.abstract as ta`:
   - SMA, EMA, RSI, MACD, BBANDS, ADX, ATR, STOCH, CCI, MFI, OBV, etc.
   - Use: ta.RSI(dataframe['close'], timeperiod=14) - pass the Series, not just timeperiod
2. qtpylib via `import qtpylib`:
   - crossed_above, crossed_below, rolling_mean, rolling_std, etc.
3. pandas_ta via `import pandas_ta as pta`:
   - Most indicators: ema, sma, rsi, macd, bbands, etc.
4. technical via `from technical.indicators import cmf, laguerre, vfi`:
   - cmf (Chaikin Money Flow), laguerre, vfi, consensus indicators
   - WARNING: EWO is NOT in technical library. Calculate manually:
     `dataframe['EWO'] = ta.EMA(dataframe['close'], 5) - ta.EMA(dataframe['close'], 35)`

API Conventions:
- Use `populate_entry_trend` and `populate_exit_trend` (not the deprecated buy/sell versions)
- Set entries with: dataframe.loc[condition, 'enter_long'] = 1
- Set exits with: dataframe.loc[condition, 'exit_long'] = 1
- For short positions use 'enter_short' and 'exit_short'

CRITICAL OUTPUT FORMAT:
- Output ONLY raw Python code
- Do NOT wrap code in markdown (no ```python or ```)
- Do NOT include explanations before or after the code
- The output must start with import statements or comments, not backticks"""


def get_code_generation_prompt(
    original_code: str,
    rag_context: str,
) -> str:
    """Get prompt for processing a new strategy."""
    return f"""Process the following Freqtrade strategy code:

## Original Strategy Code
```python
{original_code}
```

## Relevant Documentation
{rag_context}

## Your Task
1. Fix any syntax errors
2. Update deprecated API calls (populate_buy_trend -> populate_entry_trend, etc.)
3. Ensure all required methods are present
4. Keep the original trading logic intact
5. Add type hints for method parameters

Output the complete, corrected Python code (RAW CODE ONLY, NO MARKDOWN):"""


def get_code_fix_prompt(
    original_code: str,
    errors: list[str],
    rag_context: str,
) -> str:
    """Get prompt for fixing validation errors."""
    error_list = "\n".join(f"- {e}" for e in errors)

    return f"""The following strategy code has validation errors that need to be fixed:

## Current Code
```python
{original_code}
```

## Validation Errors
{error_list}

## Relevant Documentation
{rag_context}

## Your Task
Fix the validation errors while preserving the trading logic.
Make sure the code:
1. Has valid Python syntax
2. Contains a class extending IStrategy
3. Has all required methods: populate_indicators, populate_entry_trend, populate_exit_trend
4. Imports IntParameter/DecimalParameter from freqtrade.strategy (NOT from talib!)

Output the complete, fixed Python code (RAW CODE ONLY, NO MARKDOWN):"""


def get_code_evolution_prompt(
    original_code: str,
    suggestion_type: str,
    suggestion_description: str,
    rag_context: str,
    previous_errors: list[str] | None = None,
) -> str:
    """Get prompt for evolving a strategy based on diagnosis."""
    base_prompt = f"""Modify the following strategy based on the analysis recommendations:

## Current Strategy Code
```python
{original_code}
```

## Modification Request
Type: {suggestion_type}
Description: {suggestion_description}

## Relevant Documentation
{rag_context}

## Your Task
Apply the suggested modification while:
1. Keeping the existing trading logic that works well
2. Making minimal changes to achieve the goal
3. Ensuring code remains valid and complete"""

    if previous_errors:
        error_list = "\n".join(f"- {e}" for e in previous_errors)
        base_prompt += f"""

## Previous Attempt Failed With Errors
{error_list}

Make sure to fix these errors in your new attempt."""

    base_prompt += "\n\nOutput the complete, modified Python code (RAW CODE ONLY, NO MARKDOWN):"

    return base_prompt


def get_hyperopt_prompt(
    code: str,
    hardcoded_values: list[dict],
) -> str:
    """Get prompt for generating hyperopt configuration."""
    values_list = "\n".join(
        f"- Line {v['line']}: {v['value']} ({v.get('context', 'unknown')})"
        for v in hardcoded_values[:20]  # Limit to prevent huge prompts
    )

    return f"""Analyze this strategy code and identify parameters that should be optimized:

## Strategy Code
```python
{code}
```

## Detected Hardcoded Values
{values_list}

## Your Task
Identify which hardcoded values would benefit from hyperparameter optimization.
For each parameter, provide:
- A descriptive name
- The parameter type (int or float)
- A reasonable search range (low, high)
- A sensible default value

Output as JSON:
{{
  "parameters": [
    {{"name": "param_name", "type": "int", "low": 5, "high": 20, "default": 14}},
    ...
  ]
}}

Only include parameters that:
1. Are used in trading logic (not configuration like timeframe)
2. Have a meaningful impact on strategy behavior
3. Have sensible ranges that won't cause errors"""


METADATA_SYSTEM_PROMPT = """You are a quantitative trading strategy analyst.
Analyze the given Freqtrade strategy code and generate:
1. A concise description (2-3 sentences) explaining what the strategy does and its core logic
2. Classification tags for strategy type, risk level, and trading style

Output your analysis as JSON with the following structure:
{
    "description": "A concise description of the strategy...",
    "tags": {
        "strategy_type": ["trend_following"],  // Can be multiple: trend_following, momentum, mean_reversion, grid, breakout
        "risk_level": "medium",                // low, medium, or high
        "trading_style": "intraday",           // scalping, intraday, swing, or position
        "indicators": ["RSI", "EMA"],          // Detected indicators from the code
        "market_regime": []                    // Leave empty - will be filled by Analyst
    }
}

Classification Guidelines:
- Strategy Type:
  - trend_following: Uses moving average crossovers, trend indicators (ADX, Supertrend)
  - momentum: Uses RSI, MACD divergence, ROC
  - mean_reversion: Uses Bollinger Bands, oversold/overbought conditions
  - grid: Uses price levels, range trading
  - breakout: Uses support/resistance, volatility expansion

- Risk Level (based on stoploss):
  - low: stoploss <= -2%
  - medium: stoploss between -2% and -5%
  - high: stoploss > -5% or no stoploss

- Trading Style (based on timeframe):
  - scalping: 1m to 5m timeframes
  - intraday: 15m to 1h timeframes
  - swing: 4h to 1d timeframes
  - position: 1d or higher timeframes"""


def get_metadata_generation_prompt(
    code: str,
    indicators: list[str],
    timeframe: str | None,
    stoploss: float | None,
) -> str:
    """Get prompt for generating strategy description and tags."""
    indicators_str = ", ".join(indicators) if indicators else "Not detected"
    timeframe_str = timeframe or "Not specified"
    stoploss_str = f"{stoploss:.2%}" if stoploss else "Not specified"

    return f"""Analyze the following Freqtrade strategy code:

## Strategy Code
```python
{code}
```

## Extracted Metadata
- Detected Indicators: {indicators_str}
- Timeframe: {timeframe_str}
- Stoploss: {stoploss_str}

## Your Task
Generate a description and classification tags for this strategy.

The description should:
1. Explain the core trading logic in 2-3 sentences
2. Mention the key indicators or conditions used
3. Be written in a way that helps users understand what the strategy does

For tags, analyze:
1. Entry/exit logic to determine strategy type
2. Stoploss value to determine risk level
3. Timeframe to determine trading style
4. Code to confirm all detected indicators

Output as JSON (no markdown, just the JSON object):"""
