"""Engineer Agent node implementations."""

from typing import Any

import structlog

from ...core.state import EngineerState
from ...core.llm import get_llm
from ...core.messaging import publish_event, Events
from ...tools.code.parser import FreqtradeCodeParser
from ...tools.code.simhash import compute_code_hash
from .prompts import (
    get_system_prompt,
    get_code_generation_prompt,
    get_code_fix_prompt,
    get_code_evolution_prompt,
    get_hyperopt_prompt,
    get_metadata_generation_prompt,
    METADATA_SYSTEM_PROMPT,
)

logger = structlog.get_logger(__name__)


async def analyze_input_node(
    state: EngineerState,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Analyze input and determine processing approach.

    Extracts relevant information from input based on mode:
    - "new": Extract from RawStrategy
    - "evolve": Extract from DiagnosisReport

    Args:
        state: Current agent state
        config: Optional configuration

    Returns:
        State update with extracted information
    """
    input_data = state["input_data"]
    mode = state["mode"]

    logger.info("Analyzing input", mode=mode)

    if mode == "evolve":
        # Input is a DiagnosisReport
        return {
            "strategy_name": input_data.get("strategy_name", "unknown"),
            "strategy_id": input_data.get("strategy_id"),
            "original_code": input_data.get("current_code", ""),
        }
    else:
        # Input is a RawStrategy
        return {
            "strategy_name": input_data.get("name", "unknown"),
            "original_code": input_data.get("code", ""),
        }


async def rag_lookup_node(
    state: EngineerState,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Query RAG knowledge base for relevant documentation.

    Looks up Freqtrade documentation based on:
    - Indicators used in the strategy
    - Modification suggestions (for evolve mode)

    Args:
        state: Current agent state
        config: Optional configuration

    Returns:
        State update with rag_context
    """
    mode = state["mode"]
    input_data = state["input_data"]

    # TODO: Implement actual RAG lookup with PGVector
    # For now, return placeholder context

    if mode == "evolve":
        suggestion_type = input_data.get("suggestion_type", "")

        # Provide relevant documentation based on suggestion type
        rag_context = _get_documentation_for_suggestion(suggestion_type)
    else:
        # Parse original code to find indicators
        parser = FreqtradeCodeParser()
        result = parser.parse(state["original_code"])
        indicators = result.indicators_used if result.is_valid else []

        rag_context = _get_documentation_for_indicators(indicators)

    return {"rag_context": rag_context}


def _get_documentation_for_suggestion(suggestion_type: str) -> str:
    """Get relevant documentation for a modification suggestion."""
    docs = {
        "ADD_FILTER": """
# Adding Trend Filters in Freqtrade

Common trend filters:
1. EMA Filter: Only buy when price > EMA(200)
   ```python
   dataframe['ema_200'] = ta.EMA(dataframe, timeperiod=200)
   # In populate_entry_trend:
   conditions.append(dataframe['close'] > dataframe['ema_200'])
   ```

2. ADX Filter: Only trade when ADX > 25 (trending market)
   ```python
   dataframe['adx'] = ta.ADX(dataframe)
   conditions.append(dataframe['adx'] > 25)
   ```
""",
        "ADD_STOPLOSS": """
# Stoploss Configuration in Freqtrade

Static stoploss:
```python
stoploss = -0.10  # 10% loss

Trailing stoploss:
```python
trailing_stop = True
trailing_stop_positive = 0.01  # 1% profit to activate
trailing_stop_positive_offset = 0.02  # 2% profit minimum
trailing_only_offset_is_reached = True
```

Custom stoploss function:
```python
def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> float:
    if current_profit > 0.05:
        return -0.01  # 1% trailing after 5% profit
    return -0.10  # 10% stoploss otherwise
```
""",
        "ADD_INDICATOR": """
# Adding New Indicators

Common indicators with ta-lib:
```python
# RSI
dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)

# MACD
macd = ta.MACD(dataframe)
dataframe['macd'] = macd['macd']
dataframe['macdsignal'] = macd['macdsignal']

# Bollinger Bands
bollinger = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
dataframe['bb_upper'] = bollinger['upperband']
dataframe['bb_middle'] = bollinger['middleband']
dataframe['bb_lower'] = bollinger['lowerband']
```
""",
    }

    return docs.get(suggestion_type, "No specific documentation available.")


def _get_documentation_for_indicators(indicators: list[str]) -> str:
    """Get documentation for specific indicators."""
    # Simplified - in production, query vector DB
    base_doc = """
# Freqtrade Strategy Development

## Required Methods
- populate_indicators(): Calculate technical indicators
- populate_entry_trend(): Define buy conditions
- populate_exit_trend(): Define sell conditions

## Best Practices
- Use vectorized operations (no loops)
- Use bitwise operators (&, |) for conditions
- Always copy signals: dataframe.loc[condition, 'enter_long'] = 1
"""
    return base_doc


async def generate_code_node(
    state: EngineerState,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate or modify strategy code using LLM.

    Uses different prompts based on mode:
    - "new": Fix syntax and adapt to latest API
    - "fix": Fix specific validation errors
    - "evolve": Apply modifications from DiagnosisReport

    Args:
        state: Current agent state
        config: Optional configuration

    Returns:
        State update with generated_code
    """
    mode = state["mode"]
    retry_count = state["retry_count"]

    logger.info(
        "Generating code",
        mode=mode,
        retry=retry_count,
        strategy=state["strategy_name"],
    )

    # Select prompt based on mode
    if mode == "evolve":
        prompt = get_code_evolution_prompt(
            original_code=state["original_code"],
            suggestion_type=state["input_data"].get("suggestion_type", ""),
            suggestion_description=state["input_data"].get("suggestion_description", ""),
            rag_context=state["rag_context"],
            previous_errors=state["validation_errors"] if retry_count > 0 else None,
        )
    elif retry_count > 0:
        # Retry with error feedback
        prompt = get_code_fix_prompt(
            original_code=state["generated_code"] or state["original_code"],
            errors=state["validation_errors"],
            rag_context=state["rag_context"],
        )
    else:
        # New strategy processing
        prompt = get_code_generation_prompt(
            original_code=state["original_code"],
            rag_context=state["rag_context"],
        )

    # Get LLM
    llm = get_llm()

    # Generate code
    system_prompt = get_system_prompt()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    response = await llm.ainvoke(messages)

    # Extract code from response
    generated_code = _extract_code_from_response(response.content)

    return {
        "generated_code": generated_code,
        "retry_count": retry_count + 1,
    }


def _extract_code_from_response(response: str) -> str:
    """Extract Python code from LLM response.

    Handles responses that may contain markdown code blocks.

    Args:
        response: LLM response text

    Returns:
        Extracted Python code
    """
    import re

    original_response = response
    response = response.strip()

    # Check for markdown code block with python tag
    if "```python" in response:
        start = response.find("```python") + len("```python")
        end = response.find("```", start)
        if end > start:
            code = response[start:end].strip()
            logger.debug("Extracted code from ```python block", code_length=len(code))
            return code
        else:
            # No closing ```, take everything after ```python
            code = response[start:].strip()
            # Remove any trailing ``` if present
            code = re.sub(r'```\s*$', '', code).strip()
            logger.debug("Extracted code from unclosed ```python block", code_length=len(code))
            return code

    # Check for generic code block
    if "```" in response:
        start = response.find("```") + 3
        # Skip language identifier if present (e.g., ```py, ```Python)
        newline_pos = response.find("\n", start)
        if newline_pos != -1 and newline_pos - start < 20:  # Language tag is usually short
            potential_lang = response[start:newline_pos].strip().lower()
            if potential_lang in ("py", "python", "python3", ""):
                start = newline_pos + 1

        end = response.find("```", start)
        if end > start:
            code = response[start:end].strip()
            logger.debug("Extracted code from ``` block", code_length=len(code))
            return code
        else:
            # No closing ```, take everything after opening
            code = response[start:].strip()
            code = re.sub(r'```\s*$', '', code).strip()
            logger.debug("Extracted code from unclosed ``` block", code_length=len(code))
            return code

    # Strip any leading/trailing backticks that might remain
    response = response.strip('`').strip()

    # If response starts with common non-code patterns, log warning
    if response.startswith(('Sure', 'Here', 'I ', 'The ', 'This')):
        logger.warning(
            "Response appears to contain explanation text, not code",
            first_50_chars=response[:50],
        )

    return response


async def validate_code_node(
    state: EngineerState,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate the generated code.

    Checks:
    - Python syntax
    - IStrategy class present
    - Required methods present

    Args:
        state: Current agent state
        config: Optional configuration

    Returns:
        State update with validation results
    """
    code = state["generated_code"]
    parser = FreqtradeCodeParser()
    result = parser.parse(code)

    errors = []

    if result.syntax_error:
        errors.append(f"Syntax error: {result.syntax_error}")

    if not result.is_strategy:
        errors.append("No class extending IStrategy found")

    if result.required_methods_missing:
        errors.append(
            f"Missing methods: {', '.join(result.required_methods_missing)}"
        )

    validation_passed = len(errors) == 0

    logger.info(
        "Code validation",
        passed=validation_passed,
        errors=errors,
    )

    return {
        "validation_errors": errors,
        "validation_passed": validation_passed,
    }


async def generate_hyperopt_node(
    state: EngineerState,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate hyperparameter optimization configuration.

    Analyzes the strategy code to identify:
    - Existing IntParameter/DecimalParameter definitions
    - Hardcoded values that could be optimized

    Args:
        state: Current agent state
        config: Optional configuration

    Returns:
        State update with hyperopt_config
    """
    code = state["generated_code"]
    parser = FreqtradeCodeParser()
    result = parser.parse(code)

    # Get existing parameters
    existing_params = result.parameters

    # Get LLM to suggest additional parameters from hardcoded values
    if result.hardcoded_values and not existing_params:
        llm = get_llm()
        prompt = get_hyperopt_prompt(code, result.hardcoded_values)

        messages = [
            {"role": "system", "content": "You are a quantitative trading expert."},
            {"role": "user", "content": prompt},
        ]

        response = await llm.ainvoke(messages)

        # Parse response for parameter suggestions
        # In production, use structured output
        suggested_params = _parse_hyperopt_response(response.content)
    else:
        suggested_params = []

    hyperopt_config = {
        "existing_parameters": existing_params,
        "suggested_parameters": suggested_params,
        "spaces": ["buy", "sell"],
        "epochs": 100,
        "loss_function": "SharpeHyperOptLoss",
    }

    return {"hyperopt_config": hyperopt_config}


def _parse_hyperopt_response(response: str) -> list[dict]:
    """Parse LLM response for hyperopt parameters."""
    # Simplified parsing - in production, use structured output
    import json
    import re

    # Try to find JSON in response
    json_match = re.search(r"\{[\s\S]*\}", response)
    if json_match:
        try:
            data = json.loads(json_match.group())
            return data.get("parameters", [])
        except json.JSONDecodeError:
            pass

    return []


async def generate_metadata_node(
    state: EngineerState,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate description and classification tags using LLM.

    Analyzes the validated strategy code to generate:
    - A concise description explaining what the strategy does
    - Classification tags (strategy_type, risk_level, trading_style, indicators)

    Args:
        state: Current agent state
        config: Optional configuration

    Returns:
        State update with description and tags
    """
    code = state["generated_code"]
    parser = FreqtradeCodeParser()
    result = parser.parse(code)

    # Extract metadata from parsed code
    indicators = result.indicators_used if result.is_valid else []
    timeframe = result.timeframe
    stoploss = result.stoploss

    logger.info(
        "Generating metadata",
        strategy=state["strategy_name"],
        indicators=indicators,
        timeframe=timeframe,
    )

    # Get LLM for metadata generation
    llm = get_llm()
    prompt = get_metadata_generation_prompt(code, indicators, timeframe, stoploss)

    messages = [
        {"role": "system", "content": METADATA_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    response = await llm.ainvoke(messages)

    # Parse the JSON response
    metadata = _parse_metadata_response(response.content)

    logger.info(
        "Metadata generated",
        strategy=state["strategy_name"],
        description_length=len(metadata.get("description", "")),
        tags=metadata.get("tags", {}),
    )

    return {
        "description": metadata.get("description", ""),
        "tags": metadata.get("tags", {}),
    }


def _parse_metadata_response(response: str) -> dict:
    """Parse LLM response for metadata JSON.

    Args:
        response: LLM response text

    Returns:
        Parsed metadata dictionary with description and tags
    """
    import json
    import re

    # Try to find JSON in response
    json_match = re.search(r"\{[\s\S]*\}", response)
    if json_match:
        try:
            data = json.loads(json_match.group())
            return {
                "description": data.get("description", ""),
                "tags": data.get("tags", {}),
            }
        except json.JSONDecodeError:
            pass

    # Fallback: return empty metadata
    logger.warning("Failed to parse metadata response", response=response[:200])
    return {"description": "", "tags": {}}


async def submit_node(
    state: EngineerState,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Submit the processed strategy.

    Publishes strategy.ready_for_backtest event with the generated code
    and hyperopt configuration.

    Args:
        state: Current agent state
        config: Optional configuration

    Returns:
        Empty state update (no changes needed)
    """
    if not state["validation_passed"]:
        logger.warning("Not submitting - validation failed")
        return {}

    code = state["generated_code"]
    code_hash = compute_code_hash(code)

    event_data = {
        "strategy_id": state["strategy_id"],
        "strategy_name": state["strategy_name"],
        "code": code,
        "code_hash": code_hash,
        "hyperopt_config": state["hyperopt_config"],
        "description": state.get("description", ""),
        "tags": state.get("tags", {}),
        "parent_id": state["input_data"].get("parent_id"),
        "generation": state["input_data"].get("generation", 0) + 1,
    }

    await publish_event(
        routing_key=Events.STRATEGY_READY_FOR_BACKTEST,
        body=event_data,
    )

    logger.info(
        "Strategy submitted for backtest",
        strategy=state["strategy_name"],
    )

    return {}
