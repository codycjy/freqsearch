"""HTTP client for Factor API."""

from typing import Any

import httpx
import structlog

from ..config import get_settings

logger = structlog.get_logger(__name__)


class FactorClientError(Exception):
    """Base exception for Factor client errors."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class FactorClient:
    """Async HTTP client for interacting with Factor API.

    Provides methods to search, retrieve, and create quantitative factors
    from the FreqSearch backend.

    Example:
        async with FactorClient() as client:
            # Search for momentum factors
            factors = await client.search(category="momentum", limit=5)

            # Get specific factor by name
            factor = await client.get_by_name("alpha_001")

            # Get category statistics
            stats = await client.get_category_stats()
    """

    def __init__(self, base_url: str | None = None, timeout: float | None = None):
        """Initialize Factor client.

        Args:
            base_url: Base URL for Factor API. Defaults to config or http://localhost:8083/api/v1
            timeout: Request timeout in seconds. Defaults to config or 30.0
        """
        settings = get_settings()
        self._base_url = base_url or settings.factor.api_url
        self._timeout = timeout or float(settings.factor.timeout_seconds)
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def connect(self) -> None:
        """Establish HTTP client connection."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                headers={"Content-Type": "application/json"},
            )
            logger.info("Factor client connected", base_url=self._base_url)

    async def close(self) -> None:
        """Close HTTP client connection."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.info("Factor client closed")

    def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure client is connected."""
        if self._client is None:
            raise FactorClientError("Client not connected. Use 'async with FactorClient()' or call await client.connect()")
        return self._client

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute HTTP request with error handling.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            params: Query parameters
            json: JSON request body

        Returns:
            Response data as dictionary

        Raises:
            FactorClientError: On HTTP error or connection failure
        """
        client = self._ensure_client()

        try:
            response = await client.request(
                method=method,
                url=endpoint,
                params=params,
                json=json,
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            error_detail = e.response.text
            logger.error(
                "HTTP error",
                status_code=e.response.status_code,
                detail=error_detail,
                endpoint=endpoint,
            )
            raise FactorClientError(
                f"HTTP {e.response.status_code}: {error_detail}",
                status_code=e.response.status_code,
            ) from e

        except httpx.RequestError as e:
            logger.error("Request error", error=str(e), endpoint=endpoint)
            raise FactorClientError(f"Request failed: {str(e)}") from e

    async def search(
        self,
        category: str | None = None,
        signal_type: str | None = None,
        holding_period: str | None = None,
        data_requirement: str | None = None,
        market_regime: str | None = None,
        keyword: str | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Search factors with multi-dimensional filters.

        Args:
            category: Factor category (momentum/mean_reversion/volatility/volume/price_pattern)
            signal_type: Signal type (entry/exit/filter/sizing/alpha)
            holding_period: Holding period (intraday/short/medium/long)
            data_requirement: Data requirements (price_only/volume/vwap/industry/fundamental)
            market_regime: Market regime (trending/ranging/volatile/any)
            keyword: Keyword search in description
            limit: Maximum results to return (default: 10)
            offset: Number of results to skip (default: 0)

        Returns:
            List of factor dictionaries
        """
        params = {
            "limit": limit,
            "offset": offset,
        }

        # Add optional filters
        if category:
            params["category"] = category
        if signal_type:
            params["signal_type"] = signal_type
        if holding_period:
            params["holding_period"] = holding_period
        if data_requirement:
            params["data_requirement"] = data_requirement
        if market_regime:
            params["market_regime"] = market_regime
        if keyword:
            params["q"] = keyword

        logger.debug("Searching factors", params=params)

        response = await self._request("GET", "/factors", params=params)
        return response.get("factors", [])

    async def get_by_name(self, name: str) -> dict[str, Any] | None:
        """Get factor by name.

        Args:
            name: Factor name (e.g., "alpha_001")

        Returns:
            Factor dictionary or None if not found
        """
        try:
            response = await self._request("GET", f"/factors/name/{name}")
            return response.get("factor")

        except FactorClientError as e:
            if e.status_code == 404:
                return None
            raise

    async def get_by_id(self, factor_id: str) -> dict[str, Any] | None:
        """Get factor by ID.

        Args:
            factor_id: Factor UUID

        Returns:
            Factor dictionary or None if not found
        """
        try:
            response = await self._request("GET", f"/factors/{factor_id}")
            return response.get("data")

        except FactorClientError as e:
            if e.status_code == 404:
                return None
            raise

    async def get_category_stats(self) -> dict[str, int]:
        """Get count of factors per category.

        Returns:
            Dictionary mapping category names to counts
            Example: {"momentum": 30, "mean_reversion": 25, ...}
        """
        response = await self._request("GET", "/factors/categories")
        return response.get("stats", {})

    async def create(self, factor: dict[str, Any]) -> dict[str, Any]:
        """Create a new factor.

        Args:
            factor: Factor data dictionary with required fields:
                - name: Unique factor name
                - source: Factor source (e.g., "worldquant_101")
                - expression: DSL expression
                - category: Factor category
                - code_template: Python code (optional)

        Returns:
            Created factor dictionary
        """
        logger.info("Creating factor", name=factor.get("name"))
        response = await self._request("POST", "/factors", json=factor)
        return response.get("data", {})


# Singleton client instance for synchronous tool access
_global_client: FactorClient | None = None


def get_factor_client() -> FactorClient:
    """Get global FactorClient instance.

    Note: Client must be manually connected via await client.connect()
    before use in async contexts.

    Returns:
        Global FactorClient instance
    """
    global _global_client
    if _global_client is None:
        _global_client = FactorClient()
    return _global_client
