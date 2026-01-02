"""Prompt templates for Engineer Agent."""


def get_system_prompt() -> str:
    """Get the system prompt for code generation."""
    return """You are an expert Freqtrade strategy engineer for Freqtrade 2025.x.
Your job is to generate PRODUCTION-READY strategy code that runs without errors.

## CRITICAL CONSTRAINTS (MUST FOLLOW):

### 1. ONLY USE THESE IMPORTS (no other libraries allowed):
```python
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter, BooleanParameter
import talib.abstract as ta
import numpy as np
import pandas as pd
from pandas import DataFrame
from datetime import datetime
from typing import Optional
```

### 2. FORBIDDEN IMPORTS (will cause runtime errors):
- `import qtpylib` - REMOVED in Freqtrade 2025, DO NOT USE
- `from technical.indicators import *` - May not be installed
- `import pandas_ta` - May not be installed
- Any custom or third-party libraries

### 3. INDICATOR CALCULATION (use ONLY talib):
```python
# CORRECT - use talib for all indicators:
dataframe['ema_fast'] = ta.EMA(dataframe['close'], timeperiod=8)
dataframe['ema_slow'] = ta.EMA(dataframe['close'], timeperiod=21)
dataframe['rsi'] = ta.RSI(dataframe['close'], timeperiod=14)
dataframe['macd'], dataframe['macdsignal'], dataframe['macdhist'] = ta.MACD(dataframe['close'])
dataframe['atr'] = ta.ATR(dataframe['high'], dataframe['low'], dataframe['close'], timeperiod=14)
dataframe['adx'] = ta.ADX(dataframe['high'], dataframe['low'], dataframe['close'], timeperiod=14)

# For EWO (Elliott Wave Oscillator) - calculate manually:
dataframe['ewo'] = ta.EMA(dataframe['close'], timeperiod=5) - ta.EMA(dataframe['close'], timeperiod=35)

# For crossover detection - use shift() instead of qtpylib:
crossed_above = (dataframe['ema_fast'] > dataframe['ema_slow']) & (dataframe['ema_fast'].shift(1) <= dataframe['ema_slow'].shift(1))
crossed_below = (dataframe['ema_fast'] < dataframe['ema_slow']) & (dataframe['ema_fast'].shift(1) >= dataframe['ema_slow'].shift(1))
```

### 4. REQUIRED STRATEGY STRUCTURE:
```python
class MyStrategy(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = '5m'

    # Risk management - ALWAYS set these
    minimal_roi = {"0": 0.1, "30": 0.05, "60": 0.02}
    stoploss = -0.05
    trailing_stop = False

    # Keep startup_candle_count LOW (max 200) to avoid data issues
    startup_candle_count = 100

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Calculate indicators here
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[condition, 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[condition, 'exit_long'] = 1
        return dataframe
```

### 5. ENTRY/EXIT CONDITIONS (correct syntax):
```python
# CORRECT - use bitwise operators with parentheses:
condition = (
    (dataframe['rsi'] < 30) &
    (dataframe['ema_fast'] > dataframe['ema_slow']) &
    (dataframe['volume'] > 0)
)
dataframe.loc[condition, 'enter_long'] = 1

# WRONG - these will fail:
# dataframe.loc[rsi < 30, 'enter_long'] = 1  # Missing dataframe reference
# dataframe.loc[dataframe['rsi'] < 30 and dataframe['volume'] > 0, ...]  # 'and' doesn't work
```

## OUTPUT FORMAT:
- Output ONLY raw Python code, no markdown
- Code must be complete and runnable
- Start directly with imports or comments
- NO backticks, NO explanations"""


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
