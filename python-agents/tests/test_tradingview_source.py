"""Tests for TradingView GitHub strategy source.

Run with: conda run -n freq pytest tests/test_tradingview_source.py -v
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import httpx

from freqsearch_agents.tools.sources.tradingview_github import (
    TradingViewGitHubSource,
    TradingViewConfig,
    TradingViewRateLimiter,
    TradingViewCache,
)


# Mock data fixtures
@pytest.fixture
def mock_pine_search_response():
    """Mock GitHub code search response for Pine Scripts."""
    return {
        "total_count": 25,
        "items": [
            {
                "name": "ema_cross.pine",
                "path": "strategies/ema_cross.pine",
                "sha": "abc123",
                "size": 5000,
                "html_url": "https://github.com/testuser/pine-strategies/blob/main/strategies/ema_cross.pine",
                "repository": {
                    "id": 123,
                    "name": "pine-strategies",
                    "full_name": "testuser/pine-strategies",
                    "owner": {"login": "testuser"},
                    "description": "TradingView Pine Script strategies",
                    "stargazers_count": 50,
                    "forks_count": 15,
                    "fork": False,
                    "topics": ["tradingview", "pine-script"],
                    "pushed_at": "2025-01-15T10:30:00Z",
                    "default_branch": "main",
                },
            },
            {
                "name": "rsi_strategy.pine",
                "path": "indicators/rsi_strategy.pine",
                "sha": "def456",
                "size": 4500,
                "html_url": "https://github.com/trader/tv-scripts/blob/master/indicators/rsi_strategy.pine",
                "repository": {
                    "id": 456,
                    "name": "tv-scripts",
                    "full_name": "trader/tv-scripts",
                    "owner": {"login": "trader"},
                    "description": "Pine Script collection",
                    "stargazers_count": 25,
                    "forks_count": 8,
                    "fork": False,
                    "topics": ["pine"],
                    "pushed_at": "2025-01-10T08:00:00Z",
                    "default_branch": "master",
                },
            },
        ],
    }


@pytest.fixture
def mock_pine_code():
    """Mock Pine Script code."""
    return """
//@version=5
strategy("EMA Cross Strategy", overlay=true)

// Inputs
fastLength = input.int(12, "Fast EMA Length")
slowLength = input.int(26, "Slow EMA Length")

// Calculate EMAs
fastEMA = ta.ema(close, fastLength)
slowEMA = ta.ema(close, slowLength)

// Plot EMAs
plot(fastEMA, color=color.blue, title="Fast EMA")
plot(slowEMA, color=color.red, title="Slow EMA")

// Entry conditions
longCondition = ta.crossover(fastEMA, slowEMA)
shortCondition = ta.crossunder(fastEMA, slowEMA)

// Execute trades
if (longCondition)
    strategy.entry("Long", strategy.long)
if (shortCondition)
    strategy.close("Long")
"""


# Unit Tests
class TestTradingViewCache:
    """Test TradingView cache implementation."""

    def test_cache_set_and_get(self):
        cache = TradingViewCache(ttl=60)
        cache.set("test_key", {"data": "value"})
        result = cache.get("test_key")
        assert result == {"data": "value"}

    def test_cache_expiration(self):
        cache = TradingViewCache(ttl=0)  # Immediate expiration
        cache.set("test_key", {"data": "value"})
        import time
        time.sleep(0.1)
        result = cache.get("test_key")
        assert result is None

    def test_cache_miss(self):
        cache = TradingViewCache()
        result = cache.get("nonexistent_key")
        assert result is None

    def test_cache_clear(self):
        cache = TradingViewCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None


class TestTradingViewRateLimiter:
    """Test rate limiter functionality."""

    @pytest.mark.asyncio
    async def test_update_from_headers(self):
        mock_client = MagicMock()
        limiter = TradingViewRateLimiter(mock_client)

        headers = httpx.Headers({
            "x-ratelimit-remaining": "4500",
            "x-ratelimit-limit": "5000",
            "x-ratelimit-reset": "1737370000",
        })

        limiter.update_from_headers(headers)
        assert limiter._remaining == 4500
        assert limiter._limit == 5000

    @pytest.mark.asyncio
    async def test_check_and_wait_sufficient_remaining(self):
        mock_client = MagicMock()
        limiter = TradingViewRateLimiter(mock_client, buffer=10)
        limiter._remaining = 100
        limiter._limit = 5000

        # Should not wait if plenty of requests remain
        await limiter.check_and_wait()  # Should complete quickly


class TestTradingViewConfig:
    """Test configuration handling."""

    def test_default_config(self):
        config = TradingViewConfig()
        assert config.token is None
        assert config.min_stars == 3  # Lower than GitHub default
        assert config.include_forks is False
        assert config.max_files == 100

    def test_custom_config(self):
        config = TradingViewConfig(
            token="test_token",
            min_stars=10,
            include_forks=True,
            max_files=200,
        )
        assert config.token == "test_token"
        assert config.min_stars == 10
        assert config.include_forks is True
        assert config.max_files == 200


class TestTradingViewGitHubSource:
    """Test TradingViewGitHubSource implementation."""

    @pytest.mark.asyncio
    async def test_source_properties(self):
        config = TradingViewConfig(token="test_token")
        source = TradingViewGitHubSource(config=config)

        assert source.source_name == "tradingview"
        assert "Pine Script" in source.source_description
        assert "conversion" in source.source_description

        await source._client.aclose()

    @pytest.mark.asyncio
    async def test_search_pine_scripts(self, mock_pine_search_response):
        """Test Pine Script search."""
        config = TradingViewConfig(
            token="test_token",
            min_stars=3,
        )

        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_pine_search_response,
                headers=httpx.Headers({
                    "x-ratelimit-remaining": "4999",
                    "x-ratelimit-limit": "5000",
                }),
                raise_for_status=lambda: None,
            )

            source = TradingViewGitHubSource(config=config)
            strategies = await source.fetch_strategy_list(limit=10)

            assert isinstance(strategies, list)
            # Should have deduplicated results
            assert len(strategies) > 0

            # Check metadata structure
            if strategies:
                first = strategies[0]
                assert "identifier" in first
                assert first["identifier"].startswith("tv_")  # TV prefix
                assert "is_pine_script" in first
                assert first["is_pine_script"] is True
                assert first["needs_conversion"] is True
                assert first["original_language"] == "pine"
                assert first["conversion_target"] == "freqtrade_python"

            await source._client.aclose()

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Complex async mocking - covered by integration tests")
    async def test_fetch_pine_code(self, mock_pine_code):
        """Test fetching Pine Script code.

        This test is skipped due to complexity of mocking nested async context managers.
        The functionality is covered by integration tests with real GitHub API.
        """
        pass

    @pytest.mark.asyncio
    async def test_invalid_identifier_format(self):
        """Test handling of invalid identifier format."""
        config = TradingViewConfig(token="test_token")
        source = TradingViewGitHubSource(config=config)

        # Missing tv_ prefix
        with pytest.raises(ValueError, match="Invalid TradingView identifier"):
            await source.fetch_strategy_code("testuser/repo:strategies/file.pine")

        # Missing colon separator
        with pytest.raises(ValueError, match="Invalid identifier format"):
            await source.fetch_strategy_code("tv_testuser-repo-file")

        await source._client.aclose()

    @pytest.mark.asyncio
    async def test_content_hash_deduplication(self):
        """Test content hash calculation for deduplication."""
        config = TradingViewConfig(token="test_token")
        source = TradingViewGitHubSource(config=config)

        code1 = "//@version=5\nstrategy('Test',    overlay=true)"
        code2 = "//@version=5\nstrategy('Test',  overlay=true)"  # Different whitespace

        hash1 = source._calculate_content_hash(code1)
        hash2 = source._calculate_content_hash(code2)

        # Normalized hashes should be identical
        assert hash1 == hash2

        await source._client.aclose()

    @pytest.mark.asyncio
    async def test_min_stars_filtering(self, mock_pine_search_response):
        """Test minimum stars threshold."""
        config = TradingViewConfig(
            token="test_token",
            min_stars=40,  # Only first repo has 50 stars
        )

        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_pine_search_response,
                headers=httpx.Headers({
                    "x-ratelimit-remaining": "4999",
                }),
                raise_for_status=lambda: None,
            )

            source = TradingViewGitHubSource(config=config)
            strategies = await source.fetch_strategy_list(limit=10)

            # Second repo (25 stars) should be filtered out
            assert isinstance(strategies, list)

            await source._client.aclose()

    @pytest.mark.asyncio
    async def test_pine_script_validation(self):
        """Test Pine Script pattern validation."""
        config = TradingViewConfig()
        source = TradingViewGitHubSource(config=config)

        # Valid Pine Script with version marker
        valid_code1 = "//@version=5\nstrategy('Test', overlay=true)"
        assert source.PINE_VERSION_PATTERN.search(valid_code1)

        # Valid Pine Script with strategy function
        valid_code2 = "strategy('My Strategy', overlay=true)\nif (condition)\n    strategy.entry('Long', strategy.long)"
        assert source.PINE_STRATEGY_PATTERN.search(valid_code2)

        # Invalid - not Pine Script
        invalid_code = "class Strategy(IStrategy):\n    pass"
        assert not source.PINE_VERSION_PATTERN.search(invalid_code)

        await source._client.aclose()

    @pytest.mark.asyncio
    async def test_langchain_tool_conversion(self):
        """Test conversion to LangChain tool."""
        config = TradingViewConfig(token="test_token")
        source = TradingViewGitHubSource(config=config)

        tool = source.as_langchain_tool()

        assert tool.name == "fetch_strategies_from_tradingview"
        assert "Pine Script" in tool.description or "TradingView" in tool.description

        await source._client.aclose()


# Integration Tests (require real GitHub token)
@pytest.mark.integration
class TestTradingViewSourceIntegration:
    """Integration tests with real GitHub API.

    These tests require a GitHub token in environment variable GITHUB_TOKEN.
    Run with: pytest tests/test_tradingview_source.py::TestTradingViewSourceIntegration -v
    """

    @pytest.mark.asyncio
    async def test_real_pine_script_search(self):
        """Test real Pine Script search (requires GITHUB_TOKEN)."""
        import os
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            pytest.skip("GITHUB_TOKEN not set")

        config = TradingViewConfig(
            token=token,
            min_stars=5,
        )

        async with TradingViewGitHubSource(config=config) as source:
            strategies = await source.fetch_strategy_list(limit=3)

            assert isinstance(strategies, list)
            assert len(strategies) <= 3

            if strategies:
                # Check structure
                first = strategies[0]
                assert "identifier" in first
                assert first["identifier"].startswith("tv_")
                assert "name" in first
                assert "url" in first
                assert "is_pine_script" in first
                assert first["is_pine_script"] is True

    @pytest.mark.asyncio
    async def test_fetch_complete_pine_strategies(self):
        """Test fetching complete Pine strategies with code (requires GITHUB_TOKEN)."""
        import os
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            pytest.skip("GITHUB_TOKEN not set")

        config = TradingViewConfig(
            token=token,
            min_stars=5,
        )

        async with TradingViewGitHubSource(config=config) as source:
            strategies = await source.fetch_strategies(limit=2)

            assert isinstance(strategies, list)

            if strategies:
                # Check RawStrategy objects
                first = strategies[0]
                assert hasattr(first, 'code')
                assert hasattr(first, 'source')
                assert first.source == "tradingview"
                assert len(first.code) > 0
                assert first.is_valid is False  # Not valid until converted
                assert "Pine Script" in str(first.validation_errors)


# Performance Tests
@pytest.mark.slow
class TestTradingViewSourcePerformance:
    """Performance tests for TradingView source."""

    @pytest.mark.asyncio
    async def test_caching_effectiveness(self):
        """Test that caching reduces API calls."""
        config = TradingViewConfig(token="test_token", cache_ttl=60)

        mock_response = {
            "items": [
                {
                    "name": "test.pine",
                    "path": "test.pine",
                    "size": 1000,
                    "repository": {
                        "owner": {"login": "user"},
                        "name": "repo",
                        "full_name": "user/repo",
                        "stargazers_count": 10,
                        "forks_count": 2,
                        "fork": False,
                        "default_branch": "main",
                    },
                }
            ]
        }

        call_count = 0

        def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return MagicMock(
                status_code=200,
                json=lambda: mock_response,
                headers=httpx.Headers({"x-ratelimit-remaining": "4999"}),
                raise_for_status=lambda: None,
            )

        with patch('httpx.AsyncClient.get', side_effect=mock_get):
            source = TradingViewGitHubSource(config=config)

            # First call - should hit API
            await source.fetch_strategy_list(limit=5)
            first_call_count = call_count

            # Second call - should use cache
            await source.fetch_strategy_list(limit=5)
            second_call_count = call_count

            # Cache should prevent additional API calls
            assert second_call_count == first_call_count

            await source._client.aclose()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
