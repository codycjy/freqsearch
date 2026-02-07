"""Example usage of GitHub source for discovering Freqtrade strategies.

This script demonstrates how to use the GitHubSource to discover and fetch
trading strategies from GitHub repositories.

Usage:
    conda run -n freq python examples/github_source_example.py

Make sure GITHUB_TOKEN is set in your .env file for better rate limits.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from freqsearch_agents.tools.sources.github import (
    GitHubSource,
    GitHubConfig,
    GitHubSearchMode,
    fetch_from_github,
)
import structlog

# Setup logging
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging_level=20),  # INFO
)
logger = structlog.get_logger(__name__)


async def example_basic_search():
    """Example 1: Basic repository search."""
    print("\n" + "=" * 80)
    print("Example 1: Basic Repository Search")
    print("=" * 80)

    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("WARNING: GITHUB_TOKEN not set. Using unauthenticated mode (60 req/hour)")

    config = GitHubConfig(
        token=token,
        min_stars=10,  # Only repos with 10+ stars
        include_forks=False,  # Skip forked repositories
        search_mode=GitHubSearchMode.REPOSITORIES,
    )

    async with GitHubSource(config=config) as source:
        strategies = await source.fetch_strategies(limit=5, sort_by="stars")

        print(f"\nFound {len(strategies)} strategies:")
        for i, strategy in enumerate(strategies, 1):
            print(f"\n{i}. {strategy.name}")
            print(f"   Source: {strategy.source_name}")
            print(f"   URL: {strategy.source_url}")
            print(f"   Code length: {len(strategy.code)} characters")
            print(f"   Valid: {strategy.is_valid}")


async def example_code_search():
    """Example 2: Direct code file search."""
    print("\n" + "=" * 80)
    print("Example 2: Direct Code Search (More Precise)")
    print("=" * 80)

    token = os.getenv("GITHUB_TOKEN")

    config = GitHubConfig(
        token=token,
        min_stars=50,  # Higher threshold for code search
        search_mode=GitHubSearchMode.CODE,  # Search code files directly
    )

    async with GitHubSource(config=config) as source:
        strategies = await source.fetch_strategies(limit=3, sort_by="indexed")

        print(f"\nFound {len(strategies)} strategies via code search:")
        for strategy in strategies:
            print(f"\n- {strategy.name}")
            print(f"  From: {strategy.source_name}")
            # Check if strategy contains specific indicators
            if "rsi" in strategy.code.lower():
                print("  Uses: RSI indicator")
            if "ema" in strategy.code.lower():
                print("  Uses: EMA indicator")
            if "macd" in strategy.code.lower():
                print("  Uses: MACD indicator")


async def example_metadata_extraction():
    """Example 3: Extract rich metadata from strategies."""
    print("\n" + "=" * 80)
    print("Example 3: Metadata Extraction")
    print("=" * 80)

    token = os.getenv("GITHUB_TOKEN")

    config = GitHubConfig(
        token=token,
        min_stars=20,
    )

    async with GitHubSource(config=config) as source:
        # Fetch strategy list with metadata
        strategy_list = await source.fetch_strategy_list(limit=5, sort_by="stars")

        print(f"\nTop strategies by stars:")
        for item in strategy_list:
            print(f"\n{item['name']}")
            print(f"  Repository: {item.get('repo_name')}")
            print(f"  Stars: {item.get('repo_stars')}")
            print(f"  Forks: {item.get('repo_forks')}")
            print(f"  Last Updated: {item.get('repo_updated')}")
            print(f"  License: {item.get('repo_license', 'Unknown')}")
            print(f"  Topics: {', '.join(item.get('repo_topics', []))}")


async def example_langchain_tool():
    """Example 4: Use as LangChain tool."""
    print("\n" + "=" * 80)
    print("Example 4: LangChain Tool Integration")
    print("=" * 80)

    token = os.getenv("GITHUB_TOKEN")

    config = GitHubConfig(token=token, min_stars=30)
    source = GitHubSource(config=config)

    # Convert to LangChain tool
    tool = source.as_langchain_tool()

    print(f"\nTool Name: {tool.name}")
    print(f"Tool Description: {tool.description}")

    # Invoke tool
    result = await tool.ainvoke({"limit": 3, "sort_by": "stars"})
    print(f"\nTool Result:\n{result}")

    await source._client.aclose()


async def example_convenience_function():
    """Example 5: Use convenience function."""
    print("\n" + "=" * 80)
    print("Example 5: Convenience Function")
    print("=" * 80)

    token = os.getenv("GITHUB_TOKEN")

    # Simple one-liner
    strategies = await fetch_from_github(
        limit=3,
        token=token,
        min_stars=15,
    )

    print(f"\nFetched {len(strategies)} strategies:")
    for strat in strategies:
        print(f"- {strat['name']} from {strat['source_name']}")


async def example_quality_filtering():
    """Example 6: Advanced quality filtering."""
    print("\n" + "=" * 80)
    print("Example 6: Quality Filtering")
    print("=" * 80)

    token = os.getenv("GITHUB_TOKEN")

    config = GitHubConfig(
        token=token,
        min_stars=50,  # High quality threshold
        include_forks=False,
        max_file_size=100_000,  # Max 100KB per file
    )

    async with GitHubSource(config=config) as source:
        strategies = await source.fetch_strategies(limit=10, sort_by="stars")

        print(f"\nHigh-quality strategies (50+ stars):")

        # Filter for specific criteria
        high_quality = []
        for strategy in strategies:
            # Check for required methods
            has_indicators = "populate_indicators" in strategy.code
            has_entry = "populate_entry_trend" in strategy.code
            has_exit = "populate_exit_trend" in strategy.code

            if has_indicators and has_entry and has_exit:
                high_quality.append(strategy)

        print(f"Found {len(high_quality)} complete strategies with all required methods")

        for strat in high_quality[:5]:
            print(f"\n- {strat.name}")
            print(f"  Timeframe: {strat.timeframe or 'Not specified'}")
            print(f"  Stoploss: {strat.stoploss or 'Not specified'}")
            print(f"  Code size: {len(strat.code)} bytes")


async def example_deduplication():
    """Example 7: Demonstrate deduplication."""
    print("\n" + "=" * 80)
    print("Example 7: Deduplication Across Repositories")
    print("=" * 80)

    token = os.getenv("GITHUB_TOKEN")

    config = GitHubConfig(
        token=token,
        min_stars=5,
        include_forks=True,  # Include forks to demonstrate deduplication
    )

    async with GitHubSource(config=config) as source:
        strategies = await source.fetch_strategies(limit=20, sort_by="stars")

        print(f"\nFetched {len(strategies)} unique strategies")
        print("Duplicate strategies (identical code) were automatically filtered")

        # Show unique strategy names
        unique_names = set(s.name for s in strategies)
        print(f"\nUnique strategy names ({len(unique_names)}):")
        for name in sorted(unique_names)[:10]:
            print(f"  - {name}")


async def example_rate_limiting():
    """Example 8: Rate limiting demonstration."""
    print("\n" + "=" * 80)
    print("Example 8: Rate Limiting Awareness")
    print("=" * 80)

    token = os.getenv("GITHUB_TOKEN")

    if not token:
        print("WARNING: Without GITHUB_TOKEN, rate limit is 60 requests/hour")
        print("With token: 5,000 requests/hour")
        return

    config = GitHubConfig(token=token)

    async with GitHubSource(config=config) as source:
        # The source automatically handles rate limiting
        print("Fetching strategies with automatic rate limit handling...")

        strategies = await source.fetch_strategies(limit=5, sort_by="stars")

        print(f"\nSuccessfully fetched {len(strategies)} strategies")
        print("Rate limiter automatically waited if necessary")


async def main():
    """Run all examples."""
    print("\n" + "=" * 80)
    print("GitHub Source Examples for FreqSearch")
    print("=" * 80)

    examples = [
        ("Basic Search", example_basic_search),
        ("Code Search", example_code_search),
        ("Metadata Extraction", example_metadata_extraction),
        ("LangChain Tool", example_langchain_tool),
        ("Convenience Function", example_convenience_function),
        ("Quality Filtering", example_quality_filtering),
        ("Deduplication", example_deduplication),
        ("Rate Limiting", example_rate_limiting),
    ]

    print("\nAvailable examples:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"{i}. {name}")

    print("\nRunning all examples (this may take a few minutes)...")
    print("Press Ctrl+C to skip\n")

    for name, example_func in examples:
        try:
            await example_func()
            await asyncio.sleep(1)  # Brief pause between examples
        except KeyboardInterrupt:
            print("\n\nExamples interrupted by user")
            break
        except Exception as e:
            print(f"\nError in {name}: {e}")
            logger.exception(f"Error running example: {name}")

    print("\n" + "=" * 80)
    print("Examples completed!")
    print("=" * 80)


if __name__ == "__main__":
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()

    # Run examples
    asyncio.run(main())
