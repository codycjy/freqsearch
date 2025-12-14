"""Abstract base class for strategy data sources."""

from abc import ABC, abstractmethod
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from ...schemas.strategy import RawStrategy


class FetchStrategiesInput(BaseModel):
    """Input schema for fetch_strategies tool."""

    limit: int = Field(default=20, description="Maximum number of strategies to fetch")
    sort_by: str = Field(
        default="score",
        description="Sort by: score, date, name",
    )


class StrategySource(ABC):
    """Abstract base class for strategy data sources.

    All strategy sources must implement this interface to be usable
    by the Scout Agent. Sources are designed to be LangChain-compatible.
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Unique identifier for this data source.

        Returns:
            Source name (e.g., "stratninja", "github")
        """
        ...

    @property
    @abstractmethod
    def source_description(self) -> str:
        """Human-readable description of this data source.

        Returns:
            Description for LLM context
        """
        ...

    @abstractmethod
    async def fetch_strategy_list(
        self,
        limit: int = 50,
        sort_by: str = "score",
    ) -> list[dict[str, Any]]:
        """Fetch a list of available strategies.

        Args:
            limit: Maximum number of strategies to fetch
            sort_by: Sorting criteria

        Returns:
            List of strategy metadata (name, url, basic info)
        """
        ...

    @abstractmethod
    async def fetch_strategy_code(self, identifier: str) -> str:
        """Fetch the complete code for a single strategy.

        Args:
            identifier: Strategy identifier (URL or name)

        Returns:
            Python source code
        """
        ...

    async def fetch_strategies(
        self,
        limit: int = 50,
        sort_by: str = "score",
    ) -> list[RawStrategy]:
        """Fetch strategies with their complete code.

        This is the main method used by Scout Agent.

        Args:
            limit: Maximum number of strategies to fetch
            sort_by: Sorting criteria

        Returns:
            List of RawStrategy objects with code
        """
        strategy_list = await self.fetch_strategy_list(limit=limit, sort_by=sort_by)
        strategies = []

        for item in strategy_list:
            try:
                code = await self.fetch_strategy_code(item["identifier"])
                strategy = RawStrategy(
                    source=self.source_name,
                    source_url=item.get("url", ""),
                    source_name=item.get("name", "unknown"),
                    name=item.get("name", "unknown"),
                    description=item.get("description"),
                    code=code,
                    timeframe=item.get("timeframe"),
                    stoploss=item.get("stoploss"),
                )
                strategies.append(strategy)
            except Exception:
                # Skip strategies that fail to fetch
                continue

        return strategies

    def as_langchain_tool(self) -> BaseTool:
        """Convert this source to a LangChain Tool.

        Returns:
            StructuredTool instance
        """

        async def _fetch(limit: int = 20, sort_by: str = "score") -> str:
            """Fetch strategies from the data source."""
            strategies = await self.fetch_strategies(limit=limit, sort_by=sort_by)
            if not strategies:
                return f"No strategies found from {self.source_name}"

            result_lines = [
                f"Found {len(strategies)} strategies from {self.source_name}:",
                "",
            ]
            for s in strategies:
                result_lines.append(f"- {s.name}: {s.source_url}")

            return "\n".join(result_lines)

        return StructuredTool.from_function(
            coroutine=_fetch,
            name=f"fetch_strategies_from_{self.source_name}",
            description=f"Fetch trading strategies from {self.source_name}. {self.source_description}",
            args_schema=FetchStrategiesInput,
        )
