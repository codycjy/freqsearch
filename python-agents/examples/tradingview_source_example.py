"""Example usage of TradingView GitHub source.

This example demonstrates how to discover Pine Script strategies from GitHub
and prepare them for LLM-based conversion to Python/Freqtrade format.

Usage:
    conda run -n freq python examples/tradingview_source_example.py
"""

import asyncio
import os
from freqsearch_agents.tools.sources import TradingViewGitHubSource, TradingViewConfig


async def main():
    """Demonstrate TradingView GitHub source usage."""

    # Get GitHub token from environment
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        print("Warning: GITHUB_TOKEN not set. Rate limits will be very low.")
        print("Create a token at: https://github.com/settings/tokens")

    # Configure the source
    config = TradingViewConfig(
        token=github_token,
        min_stars=5,  # Lower threshold for Pine scripts
        max_files=50,
        cache_ttl=900,  # 15 minute cache
    )

    print("=== TradingView GitHub Source Example ===\n")

    # Create source (use async context manager for proper cleanup)
    async with TradingViewGitHubSource(config=config) as source:
        print(f"Source: {source.source_name}")
        print(f"Description: {source.source_description}\n")

        # Example 1: Fetch strategy list (metadata only)
        print("Example 1: Fetching Pine Script strategy list...\n")
        strategy_list = await source.fetch_strategy_list(limit=5)

        print(f"Found {len(strategy_list)} Pine Script strategies:\n")
        for i, strategy in enumerate(strategy_list, 1):
            print(f"{i}. {strategy['name']}")
            print(f"   Repository: {strategy['repo_name']}")
            print(f"   Stars: {strategy['repo_stars']}")
            print(f"   URL: {strategy['url']}")
            print(f"   Is Pine Script: {strategy['is_pine_script']}")
            print(f"   Needs Conversion: {strategy['needs_conversion']}")
            print(f"   Original Language: {strategy['original_language']}")
            print(f"   Conversion Target: {strategy['conversion_target']}")
            print()

        # Example 2: Fetch complete strategies (with code)
        print("\nExample 2: Fetching complete Pine Script strategies with code...\n")
        strategies = await source.fetch_strategies(limit=2)

        print(f"Fetched {len(strategies)} complete strategies:\n")
        for i, strategy in enumerate(strategies, 1):
            print(f"{i}. {strategy.name}")
            print(f"   Source: {strategy.source}")
            print(f"   URL: {strategy.source_url}")
            print(f"   Is Valid (for direct use): {strategy.is_valid}")
            print(f"   Validation Errors: {strategy.validation_errors}")
            print(f"   Code length: {len(strategy.code)} characters")
            print(f"   Code preview:")
            print(f"   {strategy.code[:200]}...")
            print()

        # Example 3: Fetch code for a specific strategy
        if strategy_list:
            print("\nExample 3: Fetching code for a specific strategy...\n")
            first_strategy = strategy_list[0]
            identifier = first_strategy["identifier"]

            print(f"Fetching code for: {first_strategy['name']}")
            print(f"Identifier: {identifier}\n")

            try:
                code = await source.fetch_strategy_code(identifier)
                print("Successfully fetched code!")
                print(f"Code length: {len(code)} characters")
                print(f"First 300 characters:\n{code[:300]}")
            except Exception as e:
                print(f"Error fetching code: {e}")

        # Example 4: Using as LangChain tool
        print("\n\nExample 4: Converting to LangChain tool...\n")
        tool = source.as_langchain_tool()
        print(f"Tool name: {tool.name}")
        print(f"Tool description: {tool.description}")

    print("\n=== Example Complete ===")


if __name__ == "__main__":
    asyncio.run(main())
