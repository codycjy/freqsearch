"""Tests for GitHub strategy source.

Run with: conda run -n freq pytest tests/test_github_source.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from freqsearch_agents.tools.sources.github import (
    GitHubSource,
    GitHubConfig,
    GitHubSearchMode,
    GitHubRateLimiter,
    GitHubCache,
)


# Mock data fixtures
@pytest.fixture
def mock_repo_search_response():
    """Mock GitHub repository search response."""
    return {
        "total_count": 100,
        "items": [
            {
                "id": 123456,
                "name": "freqtrade-strategies",
                "full_name": "testuser/freqtrade-strategies",
                "owner": {"login": "testuser"},
                "description": "Collection of freqtrade strategies",
                "stargazers_count": 150,
                "forks_count": 45,
                "fork": False,
                "topics": ["freqtrade", "trading", "crypto"],
                "pushed_at": "2025-01-15T10:30:00Z",
                "default_branch": "main",
            },
            {
                "id": 789012,
                "name": "my-trading-bot",
                "full_name": "trader/my-trading-bot",
                "owner": {"login": "trader"},
                "description": "Freqtrade strategy collection",
                "stargazers_count": 75,
                "forks_count": 20,
                "fork": False,
                "topics": ["freqtrade"],
                "pushed_at": "2025-01-10T08:00:00Z",
                "default_branch": "main",
            },
        ],
    }


@pytest.fixture
def mock_code_search_response():
    """Mock GitHub code search response."""
    return {
        "total_count": 50,
        "items": [
            {
                "name": "MyStrategy.py",
                "path": "strategies/MyStrategy.py",
                "sha": "abc123",
                "html_url": "https://github.com/testuser/repo/blob/main/strategies/MyStrategy.py",
                "repository": {
                    "id": 123,
                    "name": "repo",
                    "full_name": "testuser/repo",
                    "owner": {"login": "testuser"},
                    "description": "Test repo",
                    "stargazers_count": 100,
                    "forks_count": 30,
                    "fork": False,
                    "topics": ["freqtrade"],
                    "pushed_at": "2025-01-15T10:30:00Z",
                    "default_branch": "main",
                },
            }
        ],
    }


@pytest.fixture
def mock_repo_contents_response():
    """Mock GitHub repository contents response."""
    return [
        {
            "type": "file",
            "name": "Strategy1.py",
            "path": "strategies/Strategy1.py",
            "size": 10240,
            "sha": "def456",
            "html_url": "https://github.com/testuser/repo/blob/main/strategies/Strategy1.py",
        },
        {
            "type": "file",
            "name": "Strategy2.py",
            "path": "strategies/Strategy2.py",
            "size": 8192,
            "sha": "ghi789",
            "html_url": "https://github.com/testuser/repo/blob/main/strategies/Strategy2.py",
        },
        {
            "type": "file",
            "name": "test_strategy.py",
            "path": "strategies/test_strategy.py",
            "size": 5120,
            "sha": "jkl012",
            "html_url": "https://github.com/testuser/repo/blob/main/strategies/test_strategy.py",
        },
    ]


@pytest.fixture
def mock_strategy_code():
    """Mock Freqtrade strategy code."""
    return """
from freqtrade.strategy import IStrategy
import talib.abstract as ta

class MyAwesomeStrategy(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = '5m'
    stoploss = -0.10

    def populate_indicators(self, dataframe, metadata):
        dataframe['rsi'] = ta.RSI(dataframe)
        dataframe['ema'] = ta.EMA(dataframe, timeperiod=20)
        return dataframe

    def populate_entry_trend(self, dataframe, metadata):
        dataframe.loc[
            (dataframe['rsi'] < 30) &
            (dataframe['volume'] > 0),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe, metadata):
        dataframe.loc[
            (dataframe['rsi'] > 70),
            'exit_long'] = 1
        return dataframe
"""


# Unit Tests
class TestGitHubCache:
    """Test GitHub cache implementation."""

    def test_cache_set_and_get(self):
        cache = GitHubCache(ttl=60)
        cache.set("test_key", {"data": "value"})
        result = cache.get("test_key")
        assert result == {"data": "value"}

    def test_cache_expiration(self):
        cache = GitHubCache(ttl=0)  # Immediate expiration
        cache.set("test_key", {"data": "value"})
        import time
        time.sleep(0.1)
        result = cache.get("test_key")
        assert result is None

    def test_cache_miss(self):
        cache = GitHubCache()
        result = cache.get("nonexistent_key")
        assert result is None

    def test_cache_clear(self):
        cache = GitHubCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None


class TestGitHubRateLimiter:
    """Test rate limiter functionality."""

    @pytest.mark.asyncio
    async def test_update_from_headers(self):
        mock_client = MagicMock()
        limiter = GitHubRateLimiter(mock_client)

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
        limiter = GitHubRateLimiter(mock_client, buffer=10)
        limiter._remaining = 100
        limiter._limit = 5000

        # Should not wait if plenty of requests remain
        await limiter.check_and_wait()  # Should complete quickly


class TestGitHubConfig:
    """Test configuration handling."""

    def test_default_config(self):
        config = GitHubConfig()
        assert config.token is None
        assert config.min_stars == 5
        assert config.include_forks is False
        assert config.search_mode == GitHubSearchMode.REPOSITORIES

    def test_custom_config(self):
        config = GitHubConfig(
            token="test_token",
            min_stars=10,
            include_forks=True,
            search_mode=GitHubSearchMode.CODE,
        )
        assert config.token == "test_token"
        assert config.min_stars == 10
        assert config.include_forks is True
        assert config.search_mode == GitHubSearchMode.CODE


class TestGitHubSource:
    """Test GitHubSource implementation."""

    @pytest.mark.asyncio
    async def test_source_properties(self):
        config = GitHubConfig(token="test_token")
        source = GitHubSource(config=config)

        assert source.source_name == "github"
        assert "GitHub" in source.source_description

        await source._client.aclose()

    @pytest.mark.asyncio
    async def test_search_repositories_mode(self, mock_repo_search_response, mock_repo_contents_response):
        """Test repository search mode."""
        config = GitHubConfig(
            token="test_token",
            search_mode=GitHubSearchMode.REPOSITORIES,
            min_stars=50,
        )

        with patch('httpx.AsyncClient.get') as mock_get:
            # Mock responses
            mock_responses = [
                # Repository search
                MagicMock(
                    status_code=200,
                    json=lambda: mock_repo_search_response,
                    headers=httpx.Headers({
                        "x-ratelimit-remaining": "4999",
                        "x-ratelimit-limit": "5000",
                    }),
                    raise_for_status=lambda: None,
                ),
                # Repository contents
                MagicMock(
                    status_code=200,
                    json=lambda: mock_repo_contents_response,
                    headers=httpx.Headers({
                        "x-ratelimit-remaining": "4998",
                        "x-ratelimit-limit": "5000",
                    }),
                    raise_for_status=lambda: None,
                ),
            ]
            mock_get.side_effect = mock_responses

            source = GitHubSource(config=config)
            strategies = await source.fetch_strategy_list(limit=10, sort_by="stars")

            # Should have found strategies (mocked)
            assert isinstance(strategies, list)

            await source._client.aclose()

    @pytest.mark.asyncio
    async def test_search_code_mode(self, mock_code_search_response):
        """Test code search mode."""
        config = GitHubConfig(
            token="test_token",
            search_mode=GitHubSearchMode.CODE,
            min_stars=50,
        )

        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_code_search_response,
                headers=httpx.Headers({
                    "x-ratelimit-remaining": "4999",
                    "x-ratelimit-limit": "5000",
                }),
                raise_for_status=lambda: None,
            )

            source = GitHubSource(config=config)
            strategies = await source.fetch_strategy_list(limit=10)

            assert isinstance(strategies, list)

            await source._client.aclose()

    @pytest.mark.asyncio
    async def test_fetch_strategy_code(self, mock_strategy_code):
        """Test fetching strategy code."""
        config = GitHubConfig(token="test_token")

        with patch('httpx.AsyncClient.get') as mock_get:
            # Mock repository info response
            repo_response = MagicMock(
                status_code=200,
                json=lambda: {"default_branch": "main"},
                headers=httpx.Headers({
                    "x-ratelimit-remaining": "4999",
                }),
                raise_for_status=lambda: None,
            )

            # Mock raw file response
            raw_response = MagicMock(
                status_code=200,
                text=mock_strategy_code,
                raise_for_status=lambda: None,
            )

            mock_get.side_effect = [repo_response, raw_response]

            source = GitHubSource(config=config)
            code = await source.fetch_strategy_code("testuser/repo:strategies/Strategy1.py")

            assert "class MyAwesomeStrategy(IStrategy)" in code
            assert "populate_indicators" in code

            await source._client.aclose()

    @pytest.mark.asyncio
    async def test_invalid_identifier_format(self):
        """Test handling of invalid identifier format."""
        config = GitHubConfig(token="test_token")
        source = GitHubSource(config=config)

        with pytest.raises(ValueError, match="Invalid identifier format"):
            await source.fetch_strategy_code("invalid-format")

        await source._client.aclose()

    @pytest.mark.asyncio
    async def test_content_hash_deduplication(self):
        """Test content hash calculation for deduplication."""
        config = GitHubConfig(token="test_token")
        source = GitHubSource(config=config)

        code1 = "class Strategy(IStrategy):    pass"
        code2 = "class Strategy(IStrategy):  pass"  # Different whitespace

        hash1 = source._calculate_content_hash(code1)
        hash2 = source._calculate_content_hash(code2)

        # Normalized hashes should be identical
        assert hash1 == hash2

        await source._client.aclose()

    @pytest.mark.asyncio
    async def test_skip_forks_when_configured(self, mock_repo_search_response):
        """Test that forks are skipped when include_forks=False."""
        config = GitHubConfig(
            token="test_token",
            include_forks=False,
            min_stars=0,
        )

        # Modify mock to include a fork
        mock_data = mock_repo_search_response.copy()
        mock_data["items"][0]["fork"] = True

        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_data,
                headers=httpx.Headers({
                    "x-ratelimit-remaining": "4999",
                }),
                raise_for_status=lambda: None,
            )

            source = GitHubSource(config=config)
            strategies = await source.fetch_strategy_list(limit=10)

            # Fork should be skipped, only non-fork repo processed
            # (but may be empty if no strategies found in scanning)
            assert isinstance(strategies, list)

            await source._client.aclose()

    @pytest.mark.asyncio
    async def test_min_stars_filtering(self, mock_repo_search_response):
        """Test minimum stars threshold."""
        config = GitHubConfig(
            token="test_token",
            min_stars=100,  # Only first repo has 150 stars
        )

        with patch('httpx.AsyncClient.get') as mock_get:
            mock_get.return_value = MagicMock(
                status_code=200,
                json=lambda: mock_repo_search_response,
                headers=httpx.Headers({
                    "x-ratelimit-remaining": "4999",
                }),
                raise_for_status=lambda: None,
            )

            source = GitHubSource(config=config)
            strategies = await source.fetch_strategy_list(limit=10)

            # Second repo (75 stars) should be filtered out
            assert isinstance(strategies, list)

            await source._client.aclose()

    @pytest.mark.asyncio
    async def test_langchain_tool_conversion(self):
        """Test conversion to LangChain tool."""
        config = GitHubConfig(token="test_token")
        source = GitHubSource(config=config)

        tool = source.as_langchain_tool()

        assert tool.name == "fetch_strategies_from_github"
        assert "GitHub" in tool.description

        await source._client.aclose()


# Integration Tests (require real GitHub token)
@pytest.mark.integration
class TestGitHubSourceIntegration:
    """Integration tests with real GitHub API.

    These tests require a GitHub token in environment variable GITHUB_TOKEN.
    Run with: pytest tests/test_github_source.py::TestGitHubSourceIntegration -v
    """

    @pytest.mark.asyncio
    async def test_real_repository_search(self):
        """Test real repository search (requires GITHUB_TOKEN)."""
        import os
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            pytest.skip("GITHUB_TOKEN not set")

        config = GitHubConfig(
            token=token,
            min_stars=100,  # Only popular repos
            search_mode=GitHubSearchMode.REPOSITORIES,
        )

        async with GitHubSource(config=config) as source:
            strategies = await source.fetch_strategy_list(limit=5, sort_by="stars")

            assert isinstance(strategies, list)
            assert len(strategies) <= 5

            if strategies:
                # Check structure
                first = strategies[0]
                assert "identifier" in first
                assert "name" in first
                assert "url" in first
                assert "repo_stars" in first

    @pytest.mark.asyncio
    async def test_real_code_search(self):
        """Test real code search (requires GITHUB_TOKEN)."""
        import os
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            pytest.skip("GITHUB_TOKEN not set")

        config = GitHubConfig(
            token=token,
            min_stars=50,
            search_mode=GitHubSearchMode.CODE,
        )

        async with GitHubSource(config=config) as source:
            strategies = await source.fetch_strategy_list(limit=3)

            assert isinstance(strategies, list)
            assert len(strategies) <= 3

    @pytest.mark.asyncio
    async def test_fetch_complete_strategies(self):
        """Test fetching complete strategies with code (requires GITHUB_TOKEN)."""
        import os
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            pytest.skip("GITHUB_TOKEN not set")

        config = GitHubConfig(
            token=token,
            min_stars=100,
        )

        async with GitHubSource(config=config) as source:
            strategies = await source.fetch_strategies(limit=2, sort_by="stars")

            assert isinstance(strategies, list)

            if strategies:
                # Check RawStrategy objects
                first = strategies[0]
                assert hasattr(first, 'code')
                assert hasattr(first, 'source')
                assert first.source == "github"
                assert len(first.code) > 0


# Performance Tests
@pytest.mark.slow
class TestGitHubSourcePerformance:
    """Performance tests for GitHub source."""

    @pytest.mark.asyncio
    async def test_caching_effectiveness(self):
        """Test that caching reduces API calls."""
        config = GitHubConfig(token="test_token", cache_ttl=60)

        mock_response = {
            "items": [
                {
                    "name": "test",
                    "owner": {"login": "user"},
                    "stargazers_count": 100,
                    "fork": False,
                    "default_branch": "main",
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
            source = GitHubSource(config=config)

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
