"""Tests for the Freqtrade code parser."""

import pytest

from freqsearch_agents.tools.code.parser import FreqtradeCodeParser, validate_strategy_code


class TestFreqtradeCodeParser:
    """Tests for FreqtradeCodeParser."""

    def test_parse_valid_strategy(self, sample_strategy_code):
        """Test parsing a valid strategy."""
        parser = FreqtradeCodeParser()
        result = parser.parse(sample_strategy_code)

        assert result.is_valid
        assert result.is_strategy
        assert result.class_name == "SampleStrategy"
        assert "IStrategy" in result.base_classes
        assert not result.required_methods_missing
        assert "populate_indicators" in result.methods
        assert "populate_entry_trend" in result.methods
        assert "populate_exit_trend" in result.methods

    def test_parse_invalid_strategy(self, sample_invalid_strategy_code):
        """Test parsing an invalid strategy."""
        parser = FreqtradeCodeParser()
        result = parser.parse(sample_invalid_strategy_code)

        assert result.is_valid  # Syntax is valid
        assert result.is_strategy  # Has IStrategy
        assert len(result.required_methods_missing) > 0  # Missing entry/exit methods

    def test_parse_syntax_error(self):
        """Test parsing code with syntax error."""
        code = "def broken(:\n    pass"
        parser = FreqtradeCodeParser()
        result = parser.parse(code)

        assert not result.is_valid
        assert result.syntax_error is not None

    def test_extract_indicators(self, sample_strategy_code):
        """Test indicator extraction."""
        parser = FreqtradeCodeParser()
        result = parser.parse(sample_strategy_code)

        assert "RSI" in result.indicators_used or "ta" in result.indicators_used

    def test_extract_parameters(self, sample_strategy_code):
        """Test parameter extraction."""
        parser = FreqtradeCodeParser()
        result = parser.parse(sample_strategy_code)

        assert len(result.parameters) > 0
        rsi_param = next((p for p in result.parameters if "rsi" in p["name"].lower()), None)
        assert rsi_param is not None
        assert rsi_param["type"] == "IntParameter"

    def test_extract_strategy_attributes(self, sample_strategy_code):
        """Test strategy attribute extraction."""
        parser = FreqtradeCodeParser()
        result = parser.parse(sample_strategy_code)

        assert result.timeframe == "5m"
        assert result.stoploss == -0.10

    def test_detect_deprecated_api(self):
        """Test detection of deprecated API."""
        old_api_code = '''
from freqtrade.strategy import IStrategy

class OldStrategy(IStrategy):
    def populate_indicators(self, dataframe, metadata):
        return dataframe

    def populate_buy_trend(self, dataframe, metadata):
        return dataframe

    def populate_sell_trend(self, dataframe, metadata):
        return dataframe
'''
        parser = FreqtradeCodeParser()
        result = parser.parse(old_api_code)

        assert result.is_valid
        assert result.uses_deprecated_api
        assert "populate_buy_trend" in result.deprecated_methods


class TestValidateStrategyCode:
    """Tests for validate_strategy_code function."""

    def test_validate_valid_code(self, sample_strategy_code):
        """Test validating valid code."""
        is_valid, errors = validate_strategy_code(sample_strategy_code)
        assert is_valid
        assert len(errors) == 0

    def test_validate_invalid_code(self, sample_invalid_strategy_code):
        """Test validating invalid code."""
        is_valid, errors = validate_strategy_code(sample_invalid_strategy_code)
        assert not is_valid
        assert len(errors) > 0
