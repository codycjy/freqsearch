"""StratNinja data source implementation.

Fetches Freqtrade strategies from https://strat.ninja/
"""

import asyncio
import re
from typing import Any

import httpx
import structlog
from aiolimiter import AsyncLimiter
from bs4 import BeautifulSoup
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ...schemas.strategy import RawStrategy
from ...schemas.strategy import StrategySource as StrategySourceEnum
from .base import StrategySource

logger = structlog.get_logger(__name__)


class StratNinjaSource(StrategySource):
    """Strategy source for strat.ninja.

    strat.ninja is a website that indexes Freqtrade strategies from various sources.
    It provides a searchable list with metadata like timeframe, stoploss, and "Ninja Score".

    Page structure:
    - List page: https://strat.ninja/strats.php (HTML table)
    - Detail page: https://strat.ninja/overview.php?strategy=NAME
    - Code URL: https://strat.ninja/mirror/NAME.py (direct Python file)
    """

    BASE_URL = "https://strat.ninja"

    def __init__(
        self,
        timeout: float = 30.0,
        max_concurrent: int = 5,
        rate_limit: int = 10,
    ):
        """Initialize StratNinja source.

        Args:
            timeout: HTTP request timeout in seconds
            max_concurrent: Maximum number of concurrent requests
            rate_limit: Maximum requests per second
        """
        self._timeout = timeout
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._rate_limiter = AsyncLimiter(rate_limit, 1.0)
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "StratNinjaSource":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(timeout=self._timeout)
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client.

        Returns:
            Configured AsyncClient instance
        """
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    )
    async def _fetch_with_retry(self, url: str) -> httpx.Response:
        """Fetch URL with retry logic and rate limiting.

        Args:
            url: URL to fetch

        Returns:
            HTTP response

        Raises:
            httpx.HTTPStatusError: If response status is not 2xx after retries
            httpx.HTTPError: If request fails after retries
        """
        async with self._rate_limiter:
            client = await self._get_client()
            response = await client.get(url)
            response.raise_for_status()
            return response

    @property
    def source_name(self) -> str:
        return "stratninja"

    @property
    def source_description(self) -> str:
        return (
            "strat.ninja indexes Freqtrade strategies from GitHub and other sources. "
            "Strategies are ranked by 'Ninja Score' and include metadata like timeframe and stoploss."
        )

    async def fetch_strategy_list(
        self,
        limit: int = 50,
        sort_by: str = "score",
    ) -> list[dict[str, Any]]:
        """Fetch list of strategies from strat.ninja.

        Args:
            limit: Maximum number of strategies to fetch
            sort_by: Sorting criteria (currently only "score" is supported by the site)

        Returns:
            List of strategy metadata dictionaries
        """
        response = await self._fetch_with_retry(f"{self.BASE_URL}/strats.php")
        soup = BeautifulSoup(response.text, "html.parser")
        strategies: list[dict[str, Any]] = []

        # Find all strategy links in the table
        # Pattern: <a href="overview.php?strategy=NAME">NAME</a>
        for link in soup.find_all("a", href=re.compile(r"overview\.php\?strategy=")):
            if len(strategies) >= limit:
                break

            name = link.get_text(strip=True)
            if not name:
                continue

            # Extract strategy name from URL
            href = str(link.get("href", ""))
            match = re.search(r"strategy=([^&]+)", href)
            if not match:
                continue

            strategy_name = match.group(1)

            # Try to find the parent row to extract more metadata
            row = link.find_parent("tr")
            metadata = self._extract_row_metadata(row) if row else {}

            strategies.append({
                "name": strategy_name,
                "identifier": strategy_name,
                "url": f"{self.BASE_URL}/overview.php?strategy={strategy_name}",
                "timeframe": metadata.get("timeframe"),
                "stoploss": metadata.get("stoploss"),
                "score": metadata.get("score"),
                "source": metadata.get("source"),
            })

        logger.info(
            "Fetched strategy list from strat.ninja",
            count=len(strategies),
            limit=limit,
        )

        return strategies

    def _extract_row_metadata(self, row: Any) -> dict[str, Any]:
        """Extract metadata from a table row.

        Args:
            row: BeautifulSoup tr element

        Returns:
            Dictionary with extracted metadata
        """
        metadata = {}
        cells = row.find_all("td")

        # Table structure (may vary):
        # [Name, Timeframe, Stoploss, Flags, Source, Scraped, Score]
        # Use safe indexing to handle table structure changes
        try:
            # Timeframe (index 1)
            if len(cells) > 1:
                timeframe_text = cells[1].get_text(strip=True)
                if timeframe_text:
                    metadata["timeframe"] = timeframe_text

            # Stoploss (index 2)
            if len(cells) > 2:
                stoploss_text = cells[2].get_text(strip=True)
                if stoploss_text:
                    try:
                        metadata["stoploss"] = float(stoploss_text)
                    except ValueError:
                        logger.debug(
                            "Failed to parse stoploss value",
                            value=stoploss_text,
                        )

            # Source (index 4) - could be GitHub link
            if len(cells) > 4:
                source_link = cells[4].find("a")
                if source_link:
                    metadata["source"] = source_link.get("href", "")

            # Score (index 6)
            if len(cells) > 6:
                score_text = cells[6].get_text(strip=True)
                if score_text:
                    try:
                        metadata["score"] = float(score_text)
                    except ValueError:
                        logger.debug(
                            "Failed to parse score value",
                            value=score_text,
                        )
        except (IndexError, AttributeError) as e:
            logger.debug(
                "Failed to extract row metadata",
                error=str(e),
                num_cells=len(cells),
            )

        return metadata

    async def fetch_strategy_code(self, identifier: str) -> str:
        """Fetch the complete Python code for a strategy.

        The code is fetched directly from the mirror URL pattern:
        https://strat.ninja/mirror/{NAME}.py

        Args:
            identifier: Strategy name

        Returns:
            Python source code

        Raises:
            httpx.HTTPStatusError: If the strategy code cannot be fetched
        """
        code_url = f"{self.BASE_URL}/mirror/{identifier}.py"
        response = await self._fetch_with_retry(code_url)
        code = response.text

        logger.debug(
            "Fetched strategy code",
            strategy=identifier,
            code_length=len(code),
        )

        return code

    async def _fetch_single_strategy(self, item: dict[str, Any]) -> RawStrategy | None:
        """Fetch a single strategy with error handling.

        Args:
            item: Strategy metadata from fetch_strategy_list

        Returns:
            RawStrategy object or None if fetching failed
        """
        async with self._semaphore:
            try:
                code = await self.fetch_strategy_code(item["identifier"])
                strategy = RawStrategy(
                    source=StrategySourceEnum.STRATNINJA,
                    source_url=item.get("url", ""),
                    source_name=item.get("name", "unknown"),
                    name=item.get("name", "unknown"),
                    description=item.get("description"),
                    code=code,
                    timeframe=item.get("timeframe"),
                    stoploss=item.get("stoploss"),
                )
                logger.debug(
                    "Successfully fetched strategy",
                    strategy=item["identifier"],
                )
                return strategy
            except httpx.HTTPStatusError as e:
                logger.warning(
                    "Failed to fetch strategy code (HTTP error)",
                    strategy=item["identifier"],
                    status_code=e.response.status_code,
                    error=str(e),
                )
                return None
            except Exception as e:
                logger.warning(
                    "Failed to fetch strategy code (unexpected error)",
                    strategy=item["identifier"],
                    error=str(e),
                    error_type=type(e).__name__,
                )
                return None

    async def fetch_strategies(
        self,
        limit: int = 50,
        sort_by: str = "score",
    ) -> list[RawStrategy]:
        """Fetch strategies with their complete code using concurrent requests.

        This overrides the base class to implement concurrent fetching with
        rate limiting and proper error handling.

        Args:
            limit: Maximum number of strategies to fetch
            sort_by: Sorting criteria

        Returns:
            List of RawStrategy objects with code
        """
        strategy_list = await self.fetch_strategy_list(limit=limit, sort_by=sort_by)

        logger.info(
            "Starting concurrent strategy fetch",
            total_strategies=len(strategy_list),
            max_concurrent=self._semaphore._value,
            rate_limit=self._rate_limiter.max_rate,
        )

        # Fetch all strategies concurrently
        tasks = [self._fetch_single_strategy(item) for item in strategy_list]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out None values and exceptions
        strategies: list[RawStrategy] = []
        failed_count = 0
        for result in results:
            if isinstance(result, Exception):
                failed_count += 1
                logger.error(
                    "Unexpected exception during concurrent fetch",
                    error=str(result),
                    error_type=type(result).__name__,
                )
            elif isinstance(result, RawStrategy):
                strategies.append(result)
            else:
                # result is None
                failed_count += 1

        logger.info(
            "Completed concurrent strategy fetch",
            successful=len(strategies),
            failed=failed_count,
            total=len(strategy_list),
        )

        return strategies


# Convenience function for direct usage
async def fetch_from_stratninja(limit: int = 20) -> list[dict[str, Any]]:
    """Convenience function to fetch strategies from strat.ninja.

    Args:
        limit: Maximum number of strategies

    Returns:
        List of RawStrategy objects
    """
    async with StratNinjaSource() as source:
        strategies = await source.fetch_strategies(limit=limit)
        return [s.model_dump() for s in strategies]
