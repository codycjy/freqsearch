"""GitHub data source implementation.

Fetches Freqtrade strategies from GitHub repositories using the GitHub REST API.
Supports searching repositories and code, with rate limiting and caching.
"""

import asyncio
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import httpx
import structlog

from .base import StrategySource

logger = structlog.get_logger(__name__)


class GitHubSearchMode(str, Enum):
    """GitHub search mode."""

    REPOSITORIES = "repositories"  # Search repos, then scan for strategies
    CODE = "code"  # Search code files directly (more precise but limited)


@dataclass
class GitHubConfig:
    """Configuration for GitHub source."""

    token: str | None = None
    api_url: str = "https://api.github.com"
    timeout: float = 30.0
    cache_ttl: int = 900  # 15 minutes
    min_stars: int = 5
    max_file_size: int = 524288  # 512KB
    include_forks: bool = False
    search_mode: GitHubSearchMode = GitHubSearchMode.REPOSITORIES
    rate_limit_buffer: int = 10  # Keep this many requests in reserve


class GitHubRateLimiter:
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

        if self._remaining is not None and self._remaining < self._buffer:
            if self._reset_time:
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


class GitHubCache:
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


class GitHubSource(StrategySource):
    """Strategy source for GitHub repositories.

    Searches GitHub for Freqtrade strategies using the GitHub REST API.
    Supports two search modes:
    1. REPOSITORIES: Search repos with "freqtrade strategy", then scan for .py files
    2. CODE: Search code files directly with "class IStrategy" (more precise)

    Features:
    - Rate limiting with exponential backoff
    - Caching to minimize API calls
    - Rich metadata extraction (stars, contributors, license)
    - Deduplication based on content hash
    - Configurable minimum stars threshold
    """

    # Common Freqtrade strategy directory patterns
    STRATEGY_PATHS = [
        "user_data/strategies",
        "strategies",
        "freqtrade/strategies",
        "",  # root directory
    ]

    # Pattern to identify strategy classes
    STRATEGY_CLASS_PATTERN = re.compile(
        r"class\s+\w+\s*\(\s*IStrategy\s*\)",
        re.MULTILINE,
    )

    # Required methods in a valid Freqtrade strategy
    REQUIRED_METHODS = [
        "populate_indicators",
        "populate_entry_trend",
        "populate_exit_trend",
    ]

    def __init__(self, config: GitHubConfig | None = None, **kwargs):
        """Initialize GitHub source.

        Args:
            config: GitHub configuration object
            **kwargs: Individual config parameters (override config object)
        """
        # Merge config
        if config is None:
            config = GitHubConfig()

        # Override with kwargs
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)

        self._config = config
        self._cache = GitHubCache(ttl=config.cache_ttl)
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
        self._rate_limiter = GitHubRateLimiter(
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
        return "github"

    @property
    def source_description(self) -> str:
        return (
            "GitHub repository search for Freqtrade strategies. "
            "Finds strategies from public repositories with quality metrics like stars and contributors."
        )

    async def fetch_strategy_list(
        self,
        limit: int = 50,
        sort_by: str = "stars",
    ) -> list[dict[str, Any]]:
        """Fetch list of strategies from GitHub.

        Args:
            limit: Maximum number of strategies to fetch
            sort_by: Sorting criteria (stars, updated, forks)

        Returns:
            List of strategy metadata dictionaries
        """
        if self._config.search_mode == GitHubSearchMode.CODE:
            return await self._search_code(limit=limit, sort_by=sort_by)
        else:
            return await self._search_repositories(limit=limit, sort_by=sort_by)

    async def _search_repositories(
        self,
        limit: int = 50,
        sort_by: str = "stars",
    ) -> list[dict[str, Any]]:
        """Search GitHub repositories for Freqtrade strategies.

        Strategy:
        1. Search repos with query "freqtrade strategy language:python"
        2. For each repo, scan common strategy directories
        3. Extract strategy files matching IStrategy pattern

        Args:
            limit: Maximum number of strategies to fetch
            sort_by: Sort order (stars, updated, forks)

        Returns:
            List of strategy metadata
        """
        cache_key = f"search:repos:{sort_by}:{limit}"
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        strategies = []
        query = "freqtrade strategy language:python"

        # Map sort_by to GitHub API parameters
        sort_map = {
            "stars": "stars",
            "updated": "updated",
            "forks": "forks",
            "score": "stars",  # Default to stars
        }
        api_sort = sort_map.get(sort_by, "stars")

        # Search repositories
        await self._rate_limiter.check_and_wait()
        response = await self._client.get(
            "/search/repositories",
            params={
                "q": query,
                "sort": api_sort,
                "order": "desc",
                "per_page": min(30, limit),  # Max 30 repos to scan
            },
        )
        response.raise_for_status()
        self._rate_limiter.update_from_headers(response.headers)

        repos = response.json().get("items", [])

        logger.info(
            "Found repositories",
            count=len(repos),
            query=query,
            sort=api_sort,
        )

        # For each repository, find strategy files
        for repo in repos:
            if len(strategies) >= limit:
                break

            # Skip forks if configured
            if repo.get("fork") and not self._config.include_forks:
                continue

            # Check minimum stars
            if repo.get("stargazers_count", 0) < self._config.min_stars:
                continue

            # Extract strategies from this repo
            repo_strategies = await self._extract_strategies_from_repo(repo)
            strategies.extend(repo_strategies)

            if len(strategies) >= limit:
                strategies = strategies[:limit]
                break

        self._cache.set(cache_key, strategies)

        logger.info(
            "Fetched strategies from repositories",
            total_strategies=len(strategies),
            total_repos=len(repos),
        )

        return strategies

    async def _search_code(
        self,
        limit: int = 50,
        sort_by: str = "indexed",
    ) -> list[dict[str, Any]]:
        """Search GitHub code files directly for Freqtrade strategies.

        More precise than repository search but limited to 1000 results.

        Args:
            limit: Maximum number of strategies
            sort_by: Sort order (indexed only for code search)

        Returns:
            List of strategy metadata
        """
        cache_key = f"search:code:{sort_by}:{limit}"
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        strategies = []
        query = "class IStrategy freqtrade language:python"

        # Code search pagination
        per_page = min(100, limit)
        page = 1

        while len(strategies) < limit:
            await self._rate_limiter.check_and_wait()

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

                # Create strategy metadata
                strategy_meta = await self._create_strategy_metadata_from_file(
                    item, repo
                )
                if strategy_meta:
                    strategies.append(strategy_meta)

            page += 1

            # GitHub code search limited to 1000 results
            if len(items) < per_page or page > 10:
                break

        self._cache.set(cache_key, strategies)

        logger.info(
            "Fetched strategies from code search",
            count=len(strategies),
            query=query,
        )

        return strategies

    async def _extract_strategies_from_repo(
        self,
        repo: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Extract strategy files from a repository.

        Scans common Freqtrade strategy directories for .py files.

        Args:
            repo: Repository metadata from GitHub API

        Returns:
            List of strategy metadata dictionaries
        """
        strategies = []
        owner = repo["owner"]["login"]
        repo_name = repo["name"]
        default_branch = repo.get("default_branch", "main")

        logger.debug(
            "Scanning repository for strategies",
            repo=f"{owner}/{repo_name}",
        )

        # Try common strategy paths
        for path in self.STRATEGY_PATHS:
            try:
                await self._rate_limiter.check_and_wait()

                # List directory contents
                response = await self._client.get(
                    f"/repos/{owner}/{repo_name}/contents/{path}",
                    params={"ref": default_branch},
                )

                if response.status_code == 404:
                    continue  # Path doesn't exist

                response.raise_for_status()
                self._rate_limiter.update_from_headers(response.headers)

                contents = response.json()
                if not isinstance(contents, list):
                    continue

                # Filter for .py files
                for item in contents:
                    if item.get("type") != "file":
                        continue
                    if not item.get("name", "").endswith(".py"):
                        continue
                    if item.get("name", "").startswith("test_"):
                        continue  # Skip test files

                    # Check file size
                    file_size = item.get("size", 0)
                    if file_size > self._config.max_file_size:
                        logger.debug(
                            "Skipping large file",
                            file=item["name"],
                            size=file_size,
                        )
                        continue

                    # Create metadata
                    strategy_meta = await self._create_strategy_metadata_from_file(
                        item, repo
                    )
                    if strategy_meta:
                        strategies.append(strategy_meta)

            except httpx.HTTPStatusError as e:
                if e.response.status_code != 404:
                    logger.warning(
                        "Error listing repository contents",
                        repo=f"{owner}/{repo_name}",
                        path=path,
                        error=str(e),
                    )
                continue
            except Exception as e:
                logger.warning(
                    "Unexpected error scanning repository",
                    repo=f"{owner}/{repo_name}",
                    error=str(e),
                )
                continue

        return strategies

    async def _create_strategy_metadata_from_file(
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
        file_name = file_item.get("name", "unknown.py")
        default_branch = repo.get("default_branch", "main")

        # Extract strategy name from filename
        strategy_name = file_name.replace(".py", "")

        # Build URLs
        github_url = file_item.get(
            "html_url",
            f"https://github.com/{owner}/{repo_name}/blob/{default_branch}/{file_path}",
        )
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo_name}/{default_branch}/{file_path}"

        # Create identifier (repo:path)
        identifier = f"{owner}/{repo_name}:{file_path}"

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
        }

    async def fetch_strategy_code(self, identifier: str) -> str:
        """Fetch the complete Python code for a strategy.

        Uses raw.githubusercontent.com to avoid rate limits.

        Args:
            identifier: Strategy identifier (format: "owner/repo:path")

        Returns:
            Python source code

        Raises:
            ValueError: If identifier format is invalid
            httpx.HTTPStatusError: If code cannot be fetched
        """
        # Parse identifier
        if ":" not in identifier:
            raise ValueError(f"Invalid identifier format: {identifier}")

        repo_full, file_path = identifier.split(":", 1)

        # Get from metadata (if available from fetch_strategy_list)
        cache_key = f"code:{identifier}"
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        # Construct raw URL
        # Format: https://raw.githubusercontent.com/owner/repo/branch/path
        # We need to determine the default branch
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

        # Validate that it contains a strategy class
        if not self.STRATEGY_CLASS_PATTERN.search(code):
            logger.warning(
                "File does not contain IStrategy class",
                identifier=identifier,
            )
            # Still return it - validation will happen in base class

        self._cache.set(cache_key, code)

        logger.debug(
            "Fetched strategy code",
            identifier=identifier,
            code_length=len(code),
        )

        return code

    def _calculate_content_hash(self, code: str) -> str:
        """Calculate content hash for deduplication.

        Args:
            code: Python source code

        Returns:
            MD5 hash of normalized code
        """
        # Normalize code for comparison
        normalized = re.sub(r"\s+", " ", code)  # Collapse whitespace
        normalized = re.sub(r"#.*", "", normalized)  # Remove comments
        return hashlib.md5(normalized.encode()).hexdigest()

    async def fetch_strategies(
        self,
        limit: int = 50,
        sort_by: str = "stars",
    ) -> list:
        """Fetch strategies with their complete code.

        Overrides base class to add deduplication.

        Args:
            limit: Maximum number of strategies to fetch
            sort_by: Sorting criteria

        Returns:
            List of RawStrategy objects with code
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
                        "Skipping duplicate strategy",
                        name=item.get("name"),
                        hash=code_hash[:8],
                    )
                    continue

                self._seen_hashes.add(code_hash)

                # Create RawStrategy
                strategy = RawStrategy(
                    source="github",
                    source_url=item.get("url", ""),
                    source_name=item.get("repo_name", ""),
                    name=item.get("name", "unknown"),
                    description=item.get("description"),
                    code=code,
                    code_hash=code_hash,
                )
                strategies.append(strategy)

                logger.info(
                    "Fetched strategy from GitHub",
                    name=strategy.name,
                    repo=item.get("repo_name"),
                    stars=item.get("repo_stars"),
                )

            except Exception as e:
                logger.warning(
                    "Failed to fetch strategy",
                    identifier=item.get("identifier"),
                    error=str(e),
                )
                continue

        logger.info(
            "Completed GitHub strategy fetch",
            total=len(strategies),
            duplicates_skipped=len(strategy_list) - len(strategies),
        )

        return strategies


# Convenience function for direct usage
async def fetch_from_github(
    limit: int = 20,
    token: str | None = None,
    min_stars: int = 5,
) -> list[dict[str, Any]]:
    """Convenience function to fetch strategies from GitHub.

    Args:
        limit: Maximum number of strategies
        token: GitHub personal access token
        min_stars: Minimum repository stars

    Returns:
        List of RawStrategy dictionaries
    """
    config = GitHubConfig(token=token, min_stars=min_stars)
    async with GitHubSource(config=config) as source:
        strategies = await source.fetch_strategies(limit=limit)
        return [s.model_dump() for s in strategies]
