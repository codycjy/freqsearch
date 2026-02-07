"""Freqtrade strategy code parser using Python AST."""

import ast
import contextlib
import re
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def preprocess_code(code: str) -> tuple[str, dict[str, str]]:
    """Preprocess strategy code to fix common syntax issues.

    Fixes:
    - Class names starting with digits (e.g., '01_Strategy' -> 'Strategy_01')

    Args:
        code: Original Python source code

    Returns:
        Tuple of (preprocessed_code, rename_map)
        rename_map maps original class names to fixed names
    """
    rename_map: dict[str, str] = {}

    # Fix class names starting with digits
    # Pattern: class <digit><rest>(...)
    def fix_class_name(match: re.Match) -> str:
        original_name = match.group(1)
        rest = match.group(2)

        # Extract leading digits and the rest
        digit_match = re.match(r"^(\d+)_?(.*)$", original_name)
        if digit_match:
            digits = digit_match.group(1)
            name_part = digit_match.group(2) or "Strategy"
            # Create new name: name_part_digits or Strategy_digits
            new_name = f"{name_part}_{digits}" if name_part else f"Strategy_{digits}"
            rename_map[original_name] = new_name
            return f"class {new_name}{rest}"
        return match.group(0)

    # Match class definitions with names starting with digits
    pattern = r"class\s+(\d[a-zA-Z0-9_]*)(\s*\([^)]*\)\s*:)"
    preprocessed = re.sub(pattern, fix_class_name, code)

    return preprocessed, rename_map


@dataclass
class ParseResult:
    """Result of parsing a Freqtrade strategy."""

    # Validity
    is_valid: bool = False
    syntax_error: str | None = None

    # Class info
    class_name: str | None = None
    base_classes: list[str] = field(default_factory=list)
    is_strategy: bool = False

    # Methods
    methods: list[str] = field(default_factory=list)
    required_methods_present: list[str] = field(default_factory=list)
    required_methods_missing: list[str] = field(default_factory=list)

    # Indicators and parameters
    indicators_used: list[str] = field(default_factory=list)
    parameters: list[dict[str, Any]] = field(default_factory=list)
    hardcoded_values: list[dict[str, Any]] = field(default_factory=list)

    # Strategy attributes
    timeframe: str | None = None
    stoploss: float | None = None
    trailing_stop: bool | None = None
    minimal_roi: dict[str, float] | None = None

    # Code quality
    uses_deprecated_api: bool = False
    deprecated_methods: list[str] = field(default_factory=list)

    # Validation results
    signature_errors: list[str] = field(default_factory=list)
    has_valid_signals: bool = False


class FreqtradeCodeParser:
    """Parser for Freqtrade strategy Python code.

    Analyzes strategy code structure, extracts metadata, and validates
    required components are present.
    """

    # Required methods for a valid strategy
    REQUIRED_METHODS_NEW = [
        "populate_indicators",
        "populate_entry_trend",
        "populate_exit_trend",
    ]

    # Old API method names (deprecated but still valid)
    REQUIRED_METHODS_OLD = [
        "populate_indicators",
        "populate_buy_trend",
        "populate_sell_trend",
    ]

    # Common indicator patterns to detect (100+ patterns)
    INDICATOR_PATTERNS = [
        # TA-Lib Moving Averages
        (r"\bSMA\s*\(", "SMA"),
        (r"\bEMA\s*\(", "EMA"),
        (r"\bWMA\s*\(", "WMA"),
        (r"\bDEMA\s*\(", "DEMA"),
        (r"\bTEMA\s*\(", "TEMA"),
        (r"\bTRIMA\s*\(", "TRIMA"),
        (r"\bKAMA\s*\(", "KAMA"),
        (r"\bMAMA\s*\(", "MAMA"),
        (r"\bT3\s*\(", "T3"),

        # TA-Lib Momentum Indicators
        (r"\bRSI\s*\(", "RSI"),
        (r"\bMACD\s*\(", "MACD"),
        (r"\bMOM\s*\(", "Momentum"),
        (r"\bROC\s*\(", "ROC"),
        (r"\bROCP\s*\(", "ROCP"),
        (r"\bROCR\s*\(", "ROCR"),
        (r"\bROCR100\s*\(", "ROCR100"),
        (r"\bPPO\s*\(", "PPO"),
        (r"\bAPO\s*\(", "APO"),
        (r"\bCCI\s*\(", "CCI"),
        (r"\bCMO\s*\(", "CMO"),
        (r"\bMFI\s*\(", "MFI"),
        (r"\bSTOCH\s*\(", "Stochastic"),
        (r"\bSTOCHF\s*\(", "Stochastic Fast"),
        (r"\bSTOCHRSI\s*\(", "Stochastic RSI"),
        (r"\bWILLR\s*\(", "Williams %R"),
        (r"\bULTOSC\s*\(", "Ultimate Oscillator"),
        (r"\bTRIX\s*\(", "TRIX"),
        (r"\bBOP\s*\(", "Balance of Power"),

        # TA-Lib Trend Indicators
        (r"\bADX\s*\(", "ADX"),
        (r"\bADXR\s*\(", "ADXR"),
        (r"\bDX\s*\(", "DX"),
        (r"\bMINUS_DI\s*\(", "Minus DI"),
        (r"\bPLUS_DI\s*\(", "Plus DI"),
        (r"\bMINUS_DM\s*\(", "Minus DM"),
        (r"\bPLUS_DM\s*\(", "Plus DM"),
        (r"\bAROON\s*\(", "Aroon"),
        (r"\bAROONOSC\s*\(", "Aroon Oscillator"),
        (r"\bSAR\s*\(", "Parabolic SAR"),
        (r"\bSAREXT\s*\(", "Parabolic SAR Extended"),

        # TA-Lib Volatility Indicators
        (r"\bATR\s*\(", "ATR"),
        (r"\bNATR\s*\(", "Normalized ATR"),
        (r"\bTRANGE\s*\(", "True Range"),
        (r"\bBBANDS\s*\(", "Bollinger Bands"),

        # TA-Lib Volume Indicators
        (r"\bOBV\s*\(", "OBV"),
        (r"\bAD\s*\(", "Chaikin A/D"),
        (r"\bADOSC\s*\(", "Chaikin A/D Oscillator"),

        # TA-Lib Candlestick Patterns
        (r"\bCDL2CROWS\s*\(", "Two Crows"),
        (r"\bCDL3BLACKCROWS\s*\(", "Three Black Crows"),
        (r"\bCDL3INSIDE\s*\(", "Three Inside Up/Down"),
        (r"\bCDL3LINESTRIKE\s*\(", "Three-Line Strike"),
        (r"\bCDL3OUTSIDE\s*\(", "Three Outside Up/Down"),
        (r"\bCDL3STARSINSOUTH\s*\(", "Three Stars In The South"),
        (r"\bCDL3WHITESOLDIERS\s*\(", "Three Advancing White Soldiers"),
        (r"\bCDLABANDONEDBABY\s*\(", "Abandoned Baby"),
        (r"\bCDLADVANCEBLOCK\s*\(", "Advance Block"),
        (r"\bCDLBELTHOLD\s*\(", "Belt-hold"),
        (r"\bCDLBREAKAWAY\s*\(", "Breakaway"),
        (r"\bCDLCLOSINGMARUBOZU\s*\(", "Closing Marubozu"),
        (r"\bCDLCONCEALBABYSWALL\s*\(", "Concealing Baby Swallow"),
        (r"\bCDLCOUNTERATTACK\s*\(", "Counterattack"),
        (r"\bCDLDARKCLOUDCOVER\s*\(", "Dark Cloud Cover"),
        (r"\bCDLDOJI\s*\(", "Doji"),
        (r"\bCDLDOJISTAR\s*\(", "Doji Star"),
        (r"\bCDLDRAGONFLYDOJI\s*\(", "Dragonfly Doji"),
        (r"\bCDLENGULFING\s*\(", "Engulfing Pattern"),
        (r"\bCDLEVENINGDOJISTAR\s*\(", "Evening Doji Star"),
        (r"\bCDLEVENINGSTAR\s*\(", "Evening Star"),
        (r"\bCDLGAPSIDESIDEWHITE\s*\(", "Up/Down-gap side-by-side white lines"),
        (r"\bCDLGRAVESTONEDOJI\s*\(", "Gravestone Doji"),
        (r"\bCDLHAMMER\s*\(", "Hammer"),
        (r"\bCDLHANGINGMAN\s*\(", "Hanging Man"),
        (r"\bCDLHARAMI\s*\(", "Harami Pattern"),
        (r"\bCDLHARAMICROSS\s*\(", "Harami Cross Pattern"),
        (r"\bCDLHIGHWAVE\s*\(", "High-Wave Candle"),
        (r"\bCDLHIKKAKE\s*\(", "Hikkake Pattern"),
        (r"\bCDLHIKKAKEMOD\s*\(", "Modified Hikkake Pattern"),
        (r"\bCDLHOMINGPIGEON\s*\(", "Homing Pigeon"),
        (r"\bCDLIDENTICAL3CROWS\s*\(", "Identical Three Crows"),
        (r"\bCDLINNECK\s*\(", "In-Neck Pattern"),
        (r"\bCDLINVERTEDHAMMER\s*\(", "Inverted Hammer"),
        (r"\bCDLKICKING\s*\(", "Kicking"),
        (r"\bCDLKICKINGBYLENGTH\s*\(", "Kicking - bull/bear determined by the longer marubozu"),
        (r"\bCDLLADDERBOTTOM\s*\(", "Ladder Bottom"),
        (r"\bCDLLONGLEGGEDDOJI\s*\(", "Long Legged Doji"),
        (r"\bCDLLONGLINE\s*\(", "Long Line Candle"),
        (r"\bCDLMARUBOZU\s*\(", "Marubozu"),
        (r"\bCDLMATCHINGLOW\s*\(", "Matching Low"),
        (r"\bCDLMATHOLD\s*\(", "Mat Hold"),
        (r"\bCDLMORNINGDOJISTAR\s*\(", "Morning Doji Star"),
        (r"\bCDLMORNINGSTAR\s*\(", "Morning Star"),
        (r"\bCDLONNECK\s*\(", "On-Neck Pattern"),
        (r"\bCDLPIERCING\s*\(", "Piercing Pattern"),
        (r"\bCDLRICKSHAWMAN\s*\(", "Rickshaw Man"),
        (r"\bCDLRISEFALL3METHODS\s*\(", "Rising/Falling Three Methods"),
        (r"\bCDLSEPARATINGLINES\s*\(", "Separating Lines"),
        (r"\bCDLSHOOTINGSTAR\s*\(", "Shooting Star"),
        (r"\bCDLSHORTLINE\s*\(", "Short Line Candle"),
        (r"\bCDLSPINNINGTOP\s*\(", "Spinning Top"),
        (r"\bCDLSTALLEDPATTERN\s*\(", "Stalled Pattern"),
        (r"\bCDLSTICKSANDWICH\s*\(", "Stick Sandwich"),
        (r"\bCDLTAKURI\s*\(", "Takuri (Dragonfly Doji with very long lower shadow)"),
        (r"\bCDLTASUKIGAP\s*\(", "Tasuki Gap"),
        (r"\bCDLTHRUSTING\s*\(", "Thrusting Pattern"),
        (r"\bCDLTRISTAR\s*\(", "Tristar Pattern"),
        (r"\bCDLUNIQUE3RIVER\s*\(", "Unique 3 River"),
        (r"\bCDLUPSIDEGAP2CROWS\s*\(", "Upside Gap Two Crows"),
        (r"\bCDLXSIDEGAP3METHODS\s*\(", "Upside/Downside Gap Three Methods"),

        # qtpylib indicators
        (r"\bcrossed_above\s*\(", "crossed_above"),
        (r"\bcrossed_below\s*\(", "crossed_below"),
        (r"\brolling_mean\s*\(", "rolling_mean"),
        (r"\brolling_std\s*\(", "rolling_std"),
        (r"\bheikinashi\s*\(", "Heikin Ashi"),
        (r"\bweighted_bollinger_bands\s*\(", "Weighted Bollinger Bands"),
        (r"\bpvt\s*\(", "Price Volume Trend"),

        # Popular custom indicators
        (r"\bSuperTrend", "SuperTrend"),
        (r"\bIchimoku", "Ichimoku"),
        (r"\bVWAP\s*\(", "VWAP"),
        (r"\bPivot", "Pivot Points"),
        (r"\bFibonacci", "Fibonacci"),
        (r"\bDonchian", "Donchian Channel"),
        (r"\bKeltner", "Keltner Channel"),

        # Technical Analysis library (ta)
        (r"\bta\.(\w+)", "ta"),  # ta.RSI, ta.EMA, etc.
        (r"\bqtpylib\.(\w+)", "qtpylib"),  # qtpylib patterns
        (r"ta\.momentum\.", "ta.momentum"),
        (r"ta\.trend\.", "ta.trend"),
        (r"ta\.volatility\.", "ta.volatility"),
        (r"ta\.volume\.", "ta.volume"),
    ]

    # Parameter type patterns
    PARAMETER_TYPES = [
        "IntParameter",
        "DecimalParameter",
        "RealParameter",
        "CategoricalParameter",
        "BooleanParameter",
    ]

    def parse(self, code: str, strategy_name: str | None = None) -> ParseResult:
        """Parse a Freqtrade strategy code string.

        Args:
            code: Python source code string
            strategy_name: Optional name for logging purposes

        Returns:
            ParseResult with extracted information
        """
        result = ParseResult()

        # Preprocess code to fix common issues (e.g., class names starting with digits)
        preprocessed_code, rename_map = preprocess_code(code)
        if rename_map:
            logger.debug(
                "Preprocessed strategy code",
                strategy=strategy_name,
                renames=rename_map,
            )

        # Try to parse the AST
        try:
            tree = ast.parse(preprocessed_code)
            result.is_valid = True
        except SyntaxError as e:
            result.is_valid = False
            result.syntax_error = f"Line {e.lineno}: {e.msg}"
            logger.warning(
                "Syntax error in strategy code",
                strategy=strategy_name,
                error=str(e),
                line=e.lineno,
            )
            return result

        # Extract class information
        self._extract_class_info(tree, result)

        # Extract methods
        self._extract_methods(tree, result)

        # Validate required methods
        self._validate_required_methods(result)

        # Extract indicators from code
        self._extract_indicators(code, result)

        # Extract parameters
        self._extract_parameters(tree, result)

        # Extract strategy attributes
        self._extract_strategy_attributes(tree, code, result)

        # Extract hardcoded values for hyperopt
        self._extract_hardcoded_values(tree, result)

        # Check for deprecated API usage
        self._check_deprecated_api(result)

        # Validate method signatures
        result.signature_errors = self._validate_method_signatures(tree)

        # Validate signal columns
        result.has_valid_signals = self._validate_signal_columns(preprocessed_code)

        return result

    def _extract_class_info(self, tree: ast.AST, result: ParseResult) -> None:
        """Extract class name and base classes."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if it extends IStrategy
                bases = []
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        bases.append(base.id)
                    elif isinstance(base, ast.Attribute):
                        bases.append(base.attr)

                if "IStrategy" in bases:
                    result.class_name = node.name
                    result.base_classes = bases
                    result.is_strategy = True
                    break

    def _extract_methods(self, tree: ast.AST, result: ParseResult) -> None:
        """Extract all method names from the strategy class."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == result.class_name:
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        result.methods.append(item.name)

    def _validate_required_methods(self, result: ParseResult) -> None:
        """Check which required methods are present or missing."""
        # Check new API first
        new_api_present = all(m in result.methods for m in self.REQUIRED_METHODS_NEW)
        old_api_present = all(m in result.methods for m in self.REQUIRED_METHODS_OLD)

        if new_api_present:
            result.required_methods_present = self.REQUIRED_METHODS_NEW.copy()
            result.required_methods_missing = []
        elif old_api_present:
            result.required_methods_present = self.REQUIRED_METHODS_OLD.copy()
            result.required_methods_missing = []
            result.uses_deprecated_api = True
            result.deprecated_methods = ["populate_buy_trend", "populate_sell_trend"]
        else:
            # Partial implementation - find what's missing
            all_methods = set(self.REQUIRED_METHODS_NEW + self.REQUIRED_METHODS_OLD)
            present = [m for m in all_methods if m in result.methods]
            missing_new = [m for m in self.REQUIRED_METHODS_NEW if m not in result.methods]
            missing_old = [m for m in self.REQUIRED_METHODS_OLD if m not in result.methods]

            # Report the smaller set of missing methods
            if len(missing_new) <= len(missing_old):
                result.required_methods_missing = missing_new
            else:
                result.required_methods_missing = missing_old
                result.uses_deprecated_api = True

            result.required_methods_present = present

    def _extract_indicators(self, code: str, result: ParseResult) -> None:
        """Extract indicators used in the code using regex patterns."""
        indicators = set()

        for pattern, name in self.INDICATOR_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                indicators.add(name)

        result.indicators_used = sorted(indicators)

    def _extract_parameters(self, tree: ast.AST, result: ParseResult) -> None:
        """Extract IntParameter/DecimalParameter definitions."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        param_name = target.id
                        if isinstance(node.value, ast.Call):
                            func = node.value.func
                            func_name = None

                            if isinstance(func, ast.Name):
                                func_name = func.id
                            elif isinstance(func, ast.Attribute):
                                func_name = func.attr

                            if func_name in self.PARAMETER_TYPES:
                                param_info = {
                                    "name": param_name,
                                    "type": func_name,
                                    "line": node.lineno,
                                }

                                # Try to extract bounds
                                for arg in node.value.args:
                                    if isinstance(arg, ast.Constant):
                                        if "low" not in param_info:
                                            param_info["low"] = arg.value
                                        elif "high" not in param_info:
                                            param_info["high"] = arg.value

                                for kw in node.value.keywords:
                                    if kw.arg in ("low", "high", "default", "space") and isinstance(kw.value, ast.Constant):
                                        param_info[kw.arg] = kw.value.value

                                result.parameters.append(param_info)

    def _extract_strategy_attributes(
        self,
        tree: ast.AST,
        code: str,
        result: ParseResult,
    ) -> None:
        """Extract strategy-level attributes like timeframe, stoploss."""
        # Use regex for simple attributes
        timeframe_match = re.search(r"timeframe\s*=\s*['\"](\w+)['\"]", code)
        if timeframe_match:
            result.timeframe = timeframe_match.group(1)

        stoploss_match = re.search(r"stoploss\s*=\s*(-?[\d.]+)", code)
        if stoploss_match:
            with contextlib.suppress(ValueError):
                result.stoploss = float(stoploss_match.group(1))

        trailing_match = re.search(r"trailing_stop\s*=\s*(True|False)", code)
        if trailing_match:
            result.trailing_stop = trailing_match.group(1) == "True"

        # Extract minimal_roi
        roi_match = re.search(
            r"minimal_roi\s*=\s*\{([^}]+)\}",
            code,
            re.DOTALL,
        )
        if roi_match:
            try:
                roi_str = "{" + roi_match.group(1) + "}"
                # Safe eval for dict literal
                result.minimal_roi = ast.literal_eval(roi_str)
            except (ValueError, SyntaxError):
                pass

    def _extract_hardcoded_values(self, tree: ast.AST, result: ParseResult) -> None:
        """Extract hardcoded numeric values that could be hyperopt targets.

        Focuses on values in comparisons and function calls within
        populate_indicators, populate_entry_trend, populate_exit_trend.
        """
        target_methods = set(self.REQUIRED_METHODS_NEW + self.REQUIRED_METHODS_OLD)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in target_methods:
                for child in ast.walk(node):
                    # Look for numeric comparisons
                    if isinstance(child, ast.Compare):
                        for comparator in [child.left] + child.comparators:
                            if isinstance(comparator, ast.Constant) and isinstance(
                                comparator.value, (int, float)
                            ):
                                result.hardcoded_values.append({
                                    "value": comparator.value,
                                    "line": comparator.lineno,
                                    "context": "comparison",
                                })

    def _check_deprecated_api(self, result: ParseResult) -> None:
        """Check for deprecated API usage."""
        deprecated = ["populate_buy_trend", "populate_sell_trend"]

        for method in deprecated:
            if method in result.methods:
                if method not in result.deprecated_methods:
                    result.deprecated_methods.append(method)
                result.uses_deprecated_api = True

    def _validate_method_signatures(self, tree: ast.AST) -> list[str]:
        """Validate that required methods have correct signatures.

        Args:
            tree: AST tree of the parsed code

        Returns:
            List of validation error messages
        """
        errors = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                args = [a.arg for a in node.args.args]

                if node.name == "populate_indicators":
                    if args != ["self", "dataframe", "metadata"]:
                        errors.append(
                            f"populate_indicators has wrong signature: {args}, "
                            "expected ['self', 'dataframe', 'metadata']"
                        )
                elif node.name == "populate_entry_trend":
                    if args != ["self", "dataframe", "metadata"]:
                        errors.append(
                            f"populate_entry_trend has wrong signature: {args}, "
                            "expected ['self', 'dataframe', 'metadata']"
                        )
                elif node.name == "populate_exit_trend":
                    if args != ["self", "dataframe", "metadata"]:
                        errors.append(
                            f"populate_exit_trend has wrong signature: {args}, "
                            "expected ['self', 'dataframe', 'metadata']"
                        )
                elif node.name == "populate_buy_trend":
                    if args != ["self", "dataframe", "metadata"]:
                        errors.append(
                            f"populate_buy_trend has wrong signature: {args}, "
                            "expected ['self', 'dataframe', 'metadata']"
                        )
                elif node.name == "populate_sell_trend" and args != ["self", "dataframe", "metadata"]:
                    errors.append(
                        f"populate_sell_trend has wrong signature: {args}, "
                        "expected ['self', 'dataframe', 'metadata']"
                    )
        return errors

    def _validate_signal_columns(self, code: str) -> bool:
        """Validate that the strategy sets enter_long/exit_long signals.

        Args:
            code: Python source code string

        Returns:
            True if both enter_long and exit_long signals are set, False otherwise
        """
        # Support multiple patterns for setting signals
        # Use DOTALL flag to match across newlines, and \s* to handle whitespace
        enter_patterns = [
            r"['\"]enter_long['\"]\s*]\s*=",  # dataframe['enter_long'] = 1
            r"['\"]enter_long['\"]\s*\]\s*=",  # dataframe.loc[(...), 'enter_long'\n] = 1
        ]
        exit_patterns = [
            r"['\"]exit_long['\"]\s*]\s*=",  # dataframe['exit_long'] = 1
            r"['\"]exit_long['\"]\s*\]\s*=",  # dataframe.loc[(...), 'exit_long'\n] = 1
        ]

        has_enter = any(re.search(p, code, re.DOTALL) for p in enter_patterns)
        has_exit = any(re.search(p, code, re.DOTALL) for p in exit_patterns)

        return has_enter and has_exit


def validate_strategy_code(
    code: str, strategy_name: str | None = None
) -> tuple[bool, list[str]]:
    """Convenience function to validate strategy code.

    Args:
        code: Python source code
        strategy_name: Optional name for logging purposes

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    parser = FreqtradeCodeParser()
    result = parser.parse(code, strategy_name=strategy_name)

    errors = []

    if result.syntax_error:
        errors.append(f"Syntax error: {result.syntax_error}")

    if not result.is_strategy:
        errors.append("No class extending IStrategy found")

    if result.required_methods_missing:
        errors.append(
            f"Missing required methods: {', '.join(result.required_methods_missing)}"
        )

    if result.signature_errors:
        errors.extend(result.signature_errors)

    if not result.has_valid_signals:
        errors.append(
            "Missing required signal columns: strategy must set both "
            "'enter_long' and 'exit_long' columns in dataframe"
        )

    return len(errors) == 0, errors
