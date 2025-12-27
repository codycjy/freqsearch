#!/usr/bin/env python3
"""
Strategy Validation Script for FreqSearch

Quick validation without running full backtest:
1. Check Python syntax
2. Verify all imports work
3. Ensure IStrategy class can be loaded
4. Validate required methods exist

Usage:
    docker run -v /path/to/strategy.py:/strategy.py freqsearch/validator /strategy.py
"""

import sys
import json
import importlib.util
import traceback
from pathlib import Path


def validate_strategy(strategy_path: str) -> dict:
    """Validate a strategy file and return results."""
    result = {
        "valid": False,
        "errors": [],
        "warnings": [],
        "class_name": None,
    }

    path = Path(strategy_path)
    if not path.exists():
        result["errors"].append(f"File not found: {strategy_path}")
        return result

    # Read and compile (syntax check)
    try:
        code = path.read_text()
        compile(code, strategy_path, "exec")
    except SyntaxError as e:
        result["errors"].append(f"Syntax error at line {e.lineno}: {e.msg}")
        return result

    # Try to import the module
    try:
        spec = importlib.util.spec_from_file_location("strategy_module", strategy_path)
        if spec is None or spec.loader is None:
            result["errors"].append("Could not create module spec")
            return result

        module = importlib.util.module_from_spec(spec)
        sys.modules["strategy_module"] = module
        spec.loader.exec_module(module)
    except ImportError as e:
        result["errors"].append(f"Import error: {e}")
        return result
    except Exception as e:
        result["errors"].append(f"Module load error: {type(e).__name__}: {e}")
        return result

    # Find IStrategy subclass
    from freqtrade.strategy import IStrategy

    strategy_class = None
    for name, obj in vars(module).items():
        if isinstance(obj, type) and issubclass(obj, IStrategy) and obj is not IStrategy:
            strategy_class = obj
            result["class_name"] = name
            break

    if strategy_class is None:
        result["errors"].append("No class extending IStrategy found")
        return result

    # Check required methods
    required_methods = ["populate_indicators", "populate_entry_trend", "populate_exit_trend"]
    for method in required_methods:
        if not hasattr(strategy_class, method):
            result["errors"].append(f"Missing required method: {method}")

    # Check required attributes
    if not hasattr(strategy_class, "timeframe"):
        result["warnings"].append("No timeframe attribute defined")

    if not hasattr(strategy_class, "stoploss"):
        result["warnings"].append("No stoploss attribute defined")

    # All checks passed
    if not result["errors"]:
        result["valid"] = True

    return result


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"valid": False, "errors": ["Usage: validate_strategy.py <path>"]}))
        sys.exit(1)

    strategy_path = sys.argv[1]
    result = validate_strategy(strategy_path)

    print(json.dumps(result))
    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
