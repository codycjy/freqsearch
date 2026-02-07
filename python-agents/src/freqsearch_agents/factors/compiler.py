"""DSL compiler for WorldQuant-style alpha expressions.

Compiles alpha factor expressions (DSL) into executable Python functions.

Example:
    compiler = FactorCompiler()
    code = compiler.compile(
        name="alpha_001",
        expression="rank(Ts_ArgMax(SignedPower(((returns < 0) ? stddev(returns, 20) : close), 2.), 5))"
    )
    # Returns valid Python function code
"""

import ast
import re
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class FactorCompiler:
    """Compiler for WorldQuant DSL to Python code.

    Handles:
    - Function name normalization (Ts_Rank -> ts_rank)
    - Data field mapping (close -> df["close"])
    - Expression validation
    - Code generation with proper imports
    """

    # Map WorldQuant DSL function names to Python operator names
    FUNCTION_MAP: dict[str, str] = {
        # Capitalize variations -> lowercase
        "Ts_Rank": "ts_rank",
        "Ts_ArgMax": "ts_argmax",
        "Ts_ArgMin": "ts_argmin",
        "Ts_Sum": "ts_sum",
        "Ts_Mean": "ts_mean",
        "Ts_Std": "ts_std",
        "Ts_Min": "ts_min",
        "Ts_Max": "ts_max",
        "SignedPower": "signed_power",
        "Delay": "delay",
        "Delta": "delta",
        "Product": "product",
        "DecayLinear": "decay_linear",
        "Rank": "rank",
        "Scale": "scale",
        "Correlation": "correlation",
        "Covariance": "covariance",
        "Log": "log",
        "Sign": "sign",
        "Abs": "abs_",
        # Common variations
        "Sum": "ts_sum",
        "Mean": "ts_mean",
        "Sma": "ts_mean",
        "StdDev": "ts_std",
        "Std": "ts_std",
        "Min": "ts_min",
        "Max": "ts_max",
        "Corr": "correlation",
        "Cov": "covariance",
    }

    # Map data field names to DataFrame column access
    DATA_MAP: dict[str, str] = {
        # OHLCV fields
        "close": 'df["close"]',
        "open": 'df["open"]',
        "high": 'df["high"]',
        "low": 'df["low"]',
        "volume": 'df["volume"]',
        "vwap": 'df["vwap"]',
        # Computed fields
        "returns": 'df["close"].pct_change()',
        "log_returns": 'np.log(df["close"]).diff()',
        # Average daily volume (common in WQ101)
        "adv5": 'df["volume"].rolling(5).mean()',
        "adv10": 'df["volume"].rolling(10).mean()',
        "adv15": 'df["volume"].rolling(15).mean()',
        "adv20": 'df["volume"].rolling(20).mean()',
        "adv30": 'df["volume"].rolling(30).mean()',
        "adv40": 'df["volume"].rolling(40).mean()',
        "adv50": 'df["volume"].rolling(50).mean()',
        "adv60": 'df["volume"].rolling(60).mean()',
        "adv81": 'df["volume"].rolling(81).mean()',
        "adv120": 'df["volume"].rolling(120).mean()',
        "adv150": 'df["volume"].rolling(150).mean()',
        "adv180": 'df["volume"].rolling(180).mean()',
    }

    def __init__(self) -> None:
        """Initialize the compiler."""
        self._operator_deps: set[str] = set()
        self._data_deps: set[str] = set()

    def compile(
        self,
        name: str,
        expression: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Compile alpha expression to Python function.

        Args:
            name: Factor name (e.g., "alpha_001")
            expression: DSL expression string
            description: Optional description for documentation

        Returns:
            Dictionary with:
                - code: Executable Python function code
                - operator_deps: List of operators used
                - data_deps: List of data fields used
                - is_valid: Whether compilation succeeded
                - error: Error message if compilation failed

        Example:
            result = compiler.compile(
                name="alpha_001",
                expression="-1 * correlation(rank(delta(log(volume), 2)), rank((close - open) / open), 6)"
            )
            print(result["code"])
        """
        self._operator_deps.clear()
        self._data_deps.clear()

        try:
            # Normalize expression (whitespace cleanup, etc.)
            normalized_expr = self._normalize(expression)

            # Transform DSL to Python
            python_expr = self._transform(normalized_expr)

            # Generate function code
            code = self._generate_function(name, python_expr, expression, description)

            # Validate syntax
            if not self.validate(code):
                return {
                    "code": code,
                    "operator_deps": sorted(self._operator_deps),
                    "data_deps": sorted(self._data_deps),
                    "is_valid": False,
                    "error": "Generated code has invalid syntax",
                }

            return {
                "code": code,
                "operator_deps": sorted(self._operator_deps),
                "data_deps": sorted(self._data_deps),
                "is_valid": True,
                "error": None,
            }

        except Exception as e:
            logger.error("Factor compilation failed", name=name, error=str(e))
            return {
                "code": "",
                "operator_deps": [],
                "data_deps": [],
                "is_valid": False,
                "error": str(e),
            }

    def _normalize(self, expr: str) -> str:
        """Normalize expression whitespace and formatting.

        Args:
            expr: Raw expression string

        Returns:
            Normalized expression
        """
        # Remove extra whitespace
        expr = " ".join(expr.split())

        # Remove spaces around operators for cleaner look
        expr = re.sub(r"\s*([+\-*/,()><!=])\s*", r"\1", expr)

        return expr

    def _transform(self, expr: str) -> str:
        """Transform DSL expression to Python code.

        Args:
            expr: Normalized DSL expression

        Returns:
            Python expression string

        Steps:
            1. Replace function names (Ts_Rank -> ts_rank)
            2. Replace data fields (close -> df["close"])
            3. Track dependencies
        """
        code = expr

        # Step 1: Replace function names
        for dsl_name, py_name in self.FUNCTION_MAP.items():
            # Use word boundaries to avoid partial matches
            pattern = rf"\b{re.escape(dsl_name)}\b"
            if re.search(pattern, code, re.IGNORECASE):
                code = re.sub(pattern, py_name, code, flags=re.IGNORECASE)
                self._operator_deps.add(py_name)

        # Step 2: Replace data field names
        for field, accessor in self.DATA_MAP.items():
            # Use word boundaries to avoid partial matches
            pattern = rf"\b{re.escape(field)}\b"
            if re.search(pattern, code):
                code = re.sub(pattern, accessor, code)
                # Extract base field name (without rolling/pct_change)
                base_field = field.replace("adv", "volume").replace("returns", "close")
                if base_field in ["close", "open", "high", "low", "volume", "vwap"]:
                    self._data_deps.add(base_field)

        # Handle ternary operator: (condition ? true_val : false_val) -> (true_val if condition else false_val)
        code = self._convert_ternary(code)

        return code

    def _convert_ternary(self, expr: str) -> str:
        """Convert C-style ternary to Python ternary.

        Converts: (condition ? true_val : false_val)
        To:       (true_val if condition else false_val)

        Args:
            expr: Expression possibly containing ternary operators

        Returns:
            Expression with Python ternary syntax
        """
        # Pattern: (condition ? true_val : false_val)
        # This is a simplified parser - for complex nested ternaries, might need recursive parsing
        pattern = r"\(([^?]+)\?([^:]+):([^)]+)\)"

        def replace_ternary(match: re.Match) -> str:
            condition = match.group(1).strip()
            true_val = match.group(2).strip()
            false_val = match.group(3).strip()
            return f"({true_val} if {condition} else {false_val})"

        # Keep replacing until no more ternaries (handles nested cases)
        max_iterations = 10
        for _ in range(max_iterations):
            new_expr = re.sub(pattern, replace_ternary, expr)
            if new_expr == expr:
                break
            expr = new_expr

        return expr

    def _generate_function(
        self,
        name: str,
        python_expr: str,
        original_expr: str,
        description: str | None = None,
    ) -> str:
        """Generate complete Python function code.

        Args:
            name: Function name
            python_expr: Transformed Python expression
            original_expr: Original DSL expression
            description: Optional description

        Returns:
            Complete Python function as string
        """
        # Build imports based on dependencies
        imports = ["import numpy as np", "import pandas as pd"]

        # Add operator imports
        if self._operator_deps:
            operator_list = ", ".join(sorted(self._operator_deps))
            imports.append(f"from freqsearch_agents.factors.operators import {operator_list}")

        imports_str = "\n".join(imports)

        # Build docstring
        doc_lines = [f'"""{name.upper()}']
        if description:
            doc_lines.append(f"\n{description}")
        doc_lines.append(f"\n\nExpression: {original_expr}")
        if self._operator_deps:
            doc_lines.append(f"\nOperators: {', '.join(sorted(self._operator_deps))}")
        if self._data_deps:
            doc_lines.append(f"\nData: {', '.join(sorted(self._data_deps))}")
        doc_lines.append('\n"""')
        docstring = "".join(doc_lines)

        # Generate function
        function_code = f"""
{imports_str}


def {name}(df: pd.DataFrame) -> pd.Series:
    {docstring}
    return {python_expr}
"""

        return function_code.strip()

    def validate(self, code: str) -> bool:
        """Validate Python code syntax.

        Args:
            code: Python code string

        Returns:
            True if code is syntactically valid
        """
        try:
            ast.parse(code)
            return True
        except SyntaxError as e:
            logger.warning("Code validation failed", error=str(e), line=e.lineno)
            return False


# Convenience function for quick compilation
def compile_factor(
    name: str,
    expression: str,
    description: str | None = None,
) -> dict[str, Any]:
    """Compile a factor expression (convenience function).

    Args:
        name: Factor name
        expression: DSL expression
        description: Optional description

    Returns:
        Compilation result dictionary

    Example:
        result = compile_factor(
            "alpha_001",
            "rank(Ts_ArgMax(close, 5))"
        )
        if result["is_valid"]:
            print(result["code"])
    """
    compiler = FactorCompiler()
    return compiler.compile(name, expression, description)


__all__ = ["FactorCompiler", "compile_factor"]
