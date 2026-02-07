"""TradingView GitHub source implementation.

Searches GitHub for Pine Script strategies and marks them for LLM conversion to Python/Freqtrade.
Pine Scripts are trading view strategies written in Pine Script language that need to be
converted to Python before they can be used with Freqtrade.
"""

import asyncio
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import httpx
import structlog

from .base import StrategySource

logger = structlog.get_logger(__name__)


@dataclass
class TradingViewConfig:
    """Configuration for TradingView GitHub source."""

    token: str | None = None
    api_url: str = "https://api.github.com"
    timeout: float = 30.0
    cache_ttl: int = 900  # 15 minutes
    min_stars: int = 3  # Lower threshold for Pine scripts
    max_file_size: int = 524288  # 512KB
    max_files: int = 100
    include_forks: bool = False
    rate_limit_buffer: int = 10  # Keep this many requests in reserve


class TradingViewRateLimiter:
    """Handle GitHub API rate limiting with exponential backoff."""

    def __init__(self, client: httpx.AsyncClient, buffer: int = 10):
        """Initialize rate limiter.

        Args:
            client: HTTP client with auth headers
            buffer: Number of requests to keep in reserve
        """
        self._client = client
        self._buffer = buffer
        self._remaining: int | None = None
        self._reset_time: datetime | None = None
        self._limit: int | None = None

    def update_from_headers(self, headers: httpx.Headers) -> None:
        """Update rate limit state from response headers.

        Args:
            headers: Response headers containing X-RateLimit-* fields
        """
        if "x-ratelimit-remaining" in headers:
            self._remaining = int(headers["x-ratelimit-remaining"])
        if "x-ratelimit-reset" in headers:
            self._reset_time = datetime.fromtimestamp(int(headers["x-ratelimit-reset"]))
        if "x-ratelimit-limit" in headers:
            self._limit = int(headers["x-ratelimit-limit"])

        logger.debug(
            "Rate limit status",
            remaining=self._remaining,
            limit=self._limit,
            reset_time=self._reset_time,
        )

    async def check_and_wait(self) -> None:
        """Check rate limit and wait if necessary.

        Raises:
            RuntimeError: If rate limit info is not available
        """
        if self._remaining is None or self._reset_time is None:
            # Fetch current rate limit status
            await self._fetch_rate_limit()

        if self._remaining is not None and self._remaining < self._buffer and self._reset_time:
            wait_seconds = (self._reset_time - datetime.now()).total_seconds()
            if wait_seconds > 0:
                logger.warning(
                    "Rate limit approaching, waiting",
                    remaining=self._remaining,
                    wait_seconds=wait_seconds,
                )
                await asyncio.sleep(wait_seconds + 1)

    async def _fetch_rate_limit(self) -> None:
        """Fetch current rate limit status from GitHub API."""
        try:
            response = await self._client.get("/rate_limit")
            response.raise_for_status()
            data = response.json()

            core = data.get("resources", {}).get("core", {})
            self._remaining = core.get("remaining")
            self._limit = core.get("limit")
            if core.get("reset"):
                self._reset_time = datetime.fromtimestamp(core["reset"])

        except Exception as e:
            logger.warning("Failed to fetch rate limit", error=str(e))


class TradingViewCache:
    """Simple in-memory cache for GitHub API responses."""

    def __init__(self, ttl: int = 900):
        """Initialize cache.

        Args:
            ttl: Time-to-live in seconds
        """
        self._cache: dict[str, tuple[datetime, Any]] = {}
        self._ttl = ttl

    def get(self, key: str) -> Any | None:
        """Get cached value if not expired.

        Args:
            key: Cache key

        Returns:
            Cached value or None if expired/missing
        """
        if key in self._cache:
            timestamp, value = self._cache[key]
            if datetime.now() - timestamp < timedelta(seconds=self._ttl):
                logger.debug("Cache hit", key=key)
                return value
            else:
                del self._cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        """Set cached value.

        Args:
            key: Cache key
            value: Value to cache
        """
        self._cache[key] = (datetime.now(), value)
        logger.debug("Cache set", key=key)

    def clear(self) -> None:
        """Clear all cached values."""
        self._cache.clear()


class TradingViewGitHubSource(StrategySource):
    """Search GitHub for Pine Script strategies that need conversion to Python.

    Searches for Pine Script files with various patterns:
    - Files with .pine extension
    - Files containing //@version= (Pine Script marker)
    - strategy() or indicator() functions

    All discovered strategies are marked with is_pine_script=True and needs_conversion=True
    flags so the Engineer agent knows they require LLM-based conversion from Pine Script
    to Python/Freqtrade format.
    """

    BASE_URL = "https://api.github.com"
    RAW_URL = "https://raw.githubusercontent.com"

    # Pine Script patterns
    PINE_VERSION_PATTERN = re.compile(r"//@version\s*=\s*\d+", re.MULTILINE)
    PINE_STRATEGY_PATTERN = re.compile(
        r"(strategy|indicator)\s*\(",
        re.MULTILINE,
    )

    def __init__(self, config: TradingViewConfig | None = None, **kwargs):
        """Initialize TradingView GitHub source.

        Args:
            config: TradingView configuration object
            **kwargs: Individual config parameters (override config object)
        """
        # Merge config
        if config is None:
            config = TradingViewConfig()

        # Override with kwargs
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)

        self._config = config
        self._cache = TradingViewCache(ttl=config.cache_ttl)
        self._seen_hashes: set[str] = set()

        # Setup HTTP client with authentication
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if config.token:
            headers["Authorization"] = f"Bearer {config.token}"

        self._client = httpx.AsyncClient(
            base_url=config.api_url,
            headers=headers,
            timeout=config.timeout,
            follow_redirects=True,
        )
        self._rate_limiter = TradingViewRateLimiter(
            self._client,
            buffer=config.rate_limit_buffer,
        )

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self._client.aclose()

    @property
    def source_name(self) -> str:
        return "tradingview"

    @property
    def source_description(self) -> str:
        return (
            "GitHub search for TradingView Pine Script strategies. "
            "Finds Pine Script strategies that need conversion to Python/Freqtrade format. "
            "Uses LLM-based conversion from Pine Script to Python."
        )

    async def fetch_strategy_list(
        self,
        limit: int = 50,
        sort_by: str = "indexed",
    ) -> list[dict[str, Any]]:
        """Search for Pine Script files on GitHub.

        Searches for:
        - Files with .pine extension
        - Files containing //@version= (Pine Script marker)
        - strategy() or indicator() functions

        Args:
            limit: Maximum number of strategies to fetch
            sort_by: Sorting criteria (indexed is only option for code search)

        Returns:
            List of strategy metadata dictionaries
        """
        cache_key = f"search:tradingview:{sort_by}:{limit}"
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        strategies = []

        # Multiple search queries for Pine Script
        queries = [
            "strategy language:pine",
            "//@version= language:pine",
            "pine script indicator",
            "extension:pine strategy",
        ]

        for query in queries:
            if len(strategies) >= limit:
                break

            logger.info("Searching GitHub for Pine Scripts", query=query)
            results = await self._search_code(query, limit - len(strategies))
            strategies.extend(results)

        # Deduplicate by identifier
        seen_identifiers = set()
        unique_strategies = []
        for strat in strategies:
            if strat["identifier"] not in seen_identifiers:
                seen_identifiers.add(strat["identifier"])
                unique_strategies.append(strat)

        # Limit results
        unique_strategies = unique_strategies[:limit]

        self._cache.set(cache_key, unique_strategies)

        logger.info(
            "Completed TradingView GitHub search",
            total_found=len(unique_strategies),
            duplicates_removed=len(strategies) - len(unique_strategies),
        )

        return unique_strategies

    async def _search_code(
        self,
        query: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Search GitHub code files for Pine Scripts.

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of strategy metadata
        """
        strategies = []
        per_page = min(100, limit)
        page = 1

        while len(strategies) < limit:
            await self._rate_limiter.check_and_wait()

            try:
                response = await self._client.get(
                    "/search/code",
                    params={
                        "q": query,
                        "sort": "indexed",
                        "order": "desc",
                        "per_page": per_page,
                        "page": page,
                    },
                )
                response.raise_for_status()
                self._rate_limiter.update_from_headers(response.headers)

                data = response.json()
                items = data.get("items", [])

                if not items:
                    break

                # Process each code file
                for item in items:
                    if len(strategies) >= limit:
                        break

                    repo = item.get("repository", {})

                    # Skip forks if configured
                    if repo.get("fork") and not self._config.include_forks:
                        continue

                    # Check minimum stars
                    if repo.get("stargazers_count", 0) < self._config.min_stars:
                        continue

                    # Check file size
                    file_size = item.get("size", 0)
                    if file_size > self._config.max_file_size:
                        logger.debug(
                            "Skipping large file",
                            file=item.get("name"),
                            size=file_size,
                        )
                        continue

                    # Fetch and validate Pine Script content
                    strategy_meta = await self._create_strategy_metadata(item, repo)
                    if strategy_meta:
                        strategies.append(strategy_meta)

                page += 1

                # GitHub code search limited to 1000 results
                if len(items) < per_page or page > 10:
                    break

            except httpx.HTTPStatusError as e:
                logger.warning(
                    "HTTP error during code search",
                    query=query,
                    status_code=e.response.status_code,
                    error=str(e),
                )
                break
            except Exception as e:
                logger.warning(
                    "Unexpected error during code search",
                    query=query,
                    error=str(e),
                )
                break

        return strategies

    async def _create_strategy_metadata(
        self,
        file_item: dict[str, Any],
        repo: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Create strategy metadata from a file item.

        Args:
            file_item: File metadata from GitHub API
            repo: Repository metadata

        Returns:
            Strategy metadata dictionary or None if invalid
        """
        owner = repo["owner"]["login"]
        repo_name = repo["name"]
        file_path = file_item.get("path", "")
        file_name = file_item.get("name", "unknown.pine")
        default_branch = repo.get("default_branch", "main")

        # Extract strategy name from filename
        strategy_name = file_name.replace(".pine", "").replace(".txt", "")

        # Build URLs
        github_url = file_item.get(
            "html_url",
            f"https://github.com/{owner}/{repo_name}/blob/{default_branch}/{file_path}",
        )
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo_name}/{default_branch}/{file_path}"

        # Create identifier (prefixed with tv_ to distinguish from regular GitHub strategies)
        identifier = f"tv_{owner}/{repo_name}:{file_path}"

        return {
            "identifier": identifier,
            "name": strategy_name,
            "url": github_url,
            "raw_url": raw_url,
            "file_path": file_path,
            "repo_name": f"{owner}/{repo_name}",
            "repo_stars": repo.get("stargazers_count", 0),
            "repo_forks": repo.get("forks_count", 0),
            "repo_updated": repo.get("pushed_at"),
            "repo_license": repo.get("license", {}).get("name") if repo.get("license") else None,
            "repo_topics": repo.get("topics", []),
            "description": repo.get("description"),
            # CRITICAL: Mark as Pine Script needing conversion
            "is_pine_script": True,
            "needs_conversion": True,
            "original_language": "pine",
            "conversion_target": "freqtrade_python",
        }

    async def fetch_strategy_code(self, identifier: str) -> str:
        """Fetch the complete Pine Script code for a strategy.

        Uses raw.githubusercontent.com to avoid rate limits.

        Args:
            identifier: Strategy identifier (format: "tv_owner/repo:path")

        Returns:
            Pine Script source code

        Raises:
            ValueError: If identifier format is invalid
            httpx.HTTPStatusError: If code cannot be fetched
        """
        # Parse identifier (remove tv_ prefix)
        if not identifier.startswith("tv_"):
            raise ValueError(f"Invalid TradingView identifier format: {identifier}")

        identifier_without_prefix = identifier[3:]  # Remove "tv_" prefix

        if ":" not in identifier_without_prefix:
            raise ValueError(f"Invalid identifier format: {identifier}")

        repo_full, file_path = identifier_without_prefix.split(":", 1)

        # Check cache
        cache_key = f"code:{identifier}"
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        # Parse repo
        parts = repo_full.split("/")
        if len(parts) != 2:
            raise ValueError(f"Invalid repo format: {repo_full}")

        owner, repo_name = parts

        # Get repository info to find default branch
        await self._rate_limiter.check_and_wait()
        response = await self._client.get(f"/repos/{owner}/{repo_name}")
        response.raise_for_status()
        self._rate_limiter.update_from_headers(response.headers)

        repo_data = response.json()
        default_branch = repo_data.get("default_branch", "main")

        # Fetch raw content (no rate limit on raw.githubusercontent.com)
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo_name}/{default_branch}/{file_path}"

        # Use a separate client for raw content (no auth needed)
        async with httpx.AsyncClient(timeout=self._config.timeout) as raw_client:
            response = await raw_client.get(raw_url)
            response.raise_for_status()

        code = response.text

        # Validate that it looks like Pine Script
        if not (
            self.PINE_VERSION_PATTERN.search(code)
            or self.PINE_STRATEGY_PATTERN.search(code)
        ):
            logger.warning(
                "File does not appear to be Pine Script",
                identifier=identifier,
            )
            # Still return it - validation will happen in base class

        self._cache.set(cache_key, code)

        logger.debug(
            "Fetched Pine Script code",
            identifier=identifier,
            code_length=len(code),
        )

        return code

    def _calculate_content_hash(self, code: str) -> str:
        """Calculate content hash for deduplication.

        Args:
            code: Pine Script source code

        Returns:
            MD5 hash of normalized code
        """
        # Normalize code for comparison
        normalized = re.sub(r"\s+", " ", code)  # Collapse whitespace
        normalized = re.sub(r"//.*", "", normalized)  # Remove comments
        return hashlib.md5(normalized.encode()).hexdigest()

    async def fetch_strategies(
        self,
        limit: int = 50,
        sort_by: str = "indexed",
    ) -> list:
        """Fetch Pine Script strategies with their complete code.

        All strategies are marked with metadata indicating they need conversion
        from Pine Script to Python/Freqtrade format.

        Args:
            limit: Maximum number of strategies to fetch
            sort_by: Sorting criteria

        Returns:
            List of RawStrategy objects with Pine Script code
        """
        # Import here to avoid circular imports
        from ...schemas.strategy import RawStrategy

        strategy_list = await self.fetch_strategy_list(limit=limit, sort_by=sort_by)
        strategies = []
        self._seen_hashes.clear()

        for item in strategy_list:
            try:
                code = await self.fetch_strategy_code(item["identifier"])

                # Deduplication
                code_hash = self._calculate_content_hash(code)
                if code_hash in self._seen_hashes:
                    logger.debug(
                        "Skipping duplicate Pine Script",
                        name=item.get("name"),
                        hash=code_hash[:8],
                    )
                    continue

                self._seen_hashes.add(code_hash)

                # Create RawStrategy with Pine Script metadata
                # NOTE: The strategy will be invalid for direct use since it's Pine Script
                # The Engineer agent must convert it to Python first
                strategy = RawStrategy(
                    source="tradingview",
                    source_url=item.get("url", ""),
                    source_name=item.get("repo_name", ""),
                    name=item.get("name", "unknown"),
                    description=f"Pine Script strategy from {item.get('repo_name')}. "
                    f"Requires LLM conversion to Python/Freqtrade. {item.get('description', '')}",
                    code=code,
                    code_hash=code_hash,
                    is_valid=False,  # Not valid until converted
                    validation_errors=[
                        "Pine Script strategy - requires conversion to Python"
                    ],
                )
                strategies.append(strategy)

                logger.info(
                    "Fetched Pine Script from GitHub",
                    name=strategy.name,
                    repo=item.get("repo_name"),
                    stars=item.get("repo_stars"),
                    needs_conversion=True,
                )

            except Exception as e:
                logger.warning(
                    "Failed to fetch Pine Script",
                    identifier=item.get("identifier"),
                    error=str(e),
                )
                continue

        logger.info(
            "Completed TradingView GitHub strategy fetch",
            total=len(strategies),
            duplicates_skipped=len(strategy_list) - len(strategies),
        )

        return strategies


# Convenience function for direct usage
async def fetch_from_tradingview(
    limit: int = 20,
    token: str | None = None,
    min_stars: int = 3,
) -> list[dict[str, Any]]:
    """Convenience function to fetch Pine Script strategies from GitHub.

    Args:
        limit: Maximum number of strategies
        token: GitHub personal access token
        min_stars: Minimum repository stars

    Returns:
        List of RawStrategy dictionaries
    """
    config = TradingViewConfig(token=token, min_stars=min_stars)
    async with TradingViewGitHubSource(config=config) as source:
        strategies = await source.fetch_strategies(limit=limit)
        return [s.model_dump() for s in strategies]
