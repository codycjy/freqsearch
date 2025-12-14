"""StratNinja data source implementation.

Fetches Freqtrade strategies from https://strat.ninja/
"""

import re
from typing import Any

import httpx
from bs4 import BeautifulSoup
import structlog

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

    def __init__(self, timeout: float = 30.0):
        """Initialize StratNinja source.

        Args:
            timeout: HTTP request timeout in seconds
        """
        self._timeout = timeout

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
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(f"{self.BASE_URL}/strats.php")
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        strategies = []

        # Find all strategy links in the table
        # Pattern: <a href="overview.php?strategy=NAME">NAME</a>
        for link in soup.find_all("a", href=re.compile(r"overview\.php\?strategy=")):
            if len(strategies) >= limit:
                break

            name = link.get_text(strip=True)
            if not name:
                continue

            # Extract strategy name from URL
            href = link.get("href", "")
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

    def _extract_row_metadata(self, row) -> dict[str, Any]:
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
        if len(cells) >= 7:
            try:
                # Timeframe (index 1)
                timeframe_text = cells[1].get_text(strip=True)
                if timeframe_text:
                    metadata["timeframe"] = timeframe_text

                # Stoploss (index 2)
                stoploss_text = cells[2].get_text(strip=True)
                if stoploss_text:
                    try:
                        metadata["stoploss"] = float(stoploss_text)
                    except ValueError:
                        pass

                # Source (index 4) - could be GitHub link
                source_link = cells[4].find("a")
                if source_link:
                    metadata["source"] = source_link.get("href", "")

                # Score (index 6)
                score_text = cells[6].get_text(strip=True)
                if score_text:
                    try:
                        metadata["score"] = float(score_text)
                    except ValueError:
                        pass
            except (IndexError, AttributeError):
                pass

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

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(code_url)
            response.raise_for_status()

        code = response.text

        logger.debug(
            "Fetched strategy code",
            strategy=identifier,
            code_length=len(code),
        )

        return code


# Convenience function for direct usage
async def fetch_from_stratninja(limit: int = 20) -> list[dict[str, Any]]:
    """Convenience function to fetch strategies from strat.ninja.

    Args:
        limit: Maximum number of strategies

    Returns:
        List of RawStrategy objects
    """
    source = StratNinjaSource()
    strategies = await source.fetch_strategies(limit=limit)
    return [s.model_dump() for s in strategies]
