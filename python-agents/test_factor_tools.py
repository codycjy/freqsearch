"""Test script for Factor client and LangChain tools."""

import asyncio
from src.freqsearch_agents.factors import (
    FactorClient,
    search_factors,
    get_factor_code,
    list_factor_categories,
)


async def test_client():
    """Test FactorClient async operations."""
    print("\n=== Testing FactorClient ===\n")

    async with FactorClient() as client:
        print("✓ Client connected successfully")

        # Test search
        print("\nSearching for momentum factors...")
        try:
            factors = await client.search(category="momentum", limit=3)
            print(f"Found {len(factors)} factors")
            for f in factors:
                print(f"  - {f.get('name')}: {f.get('description', 'N/A')[:50]}")
        except Exception as e:
            print(f"✗ Search failed: {e}")

        # Test get_by_name
        print("\nGetting factor by name (alpha_001)...")
        try:
            factor = await client.get_by_name("alpha_001")
            if factor:
                print(f"✓ Found factor: {factor.get('name')}")
            else:
                print("✗ Factor not found (expected if backend not running)")
        except Exception as e:
            print(f"✗ Get by name failed: {e}")

        # Test category stats
        print("\nGetting category statistics...")
        try:
            stats = await client.get_category_stats()
            print(f"✓ Category stats: {stats}")
        except Exception as e:
            print(f"✗ Category stats failed: {e}")


def test_tools():
    """Test LangChain tools (sync wrappers)."""
    print("\n=== Testing LangChain Tools ===\n")

    # Test search_factors tool
    print("Testing search_factors tool...")
    try:
        result = search_factors.invoke({
            "category": "momentum",
            "limit": 2
        })
        print(f"✓ search_factors result:\n{result[:200]}...")
    except Exception as e:
        print(f"✗ search_factors failed: {e}")

    # Test get_factor_code tool
    print("\nTesting get_factor_code tool...")
    try:
        result = get_factor_code.invoke({"factor_name": "alpha_001"})
        print(f"✓ get_factor_code result:\n{result[:200]}...")
    except Exception as e:
        print(f"✗ get_factor_code failed: {e}")

    # Test list_factor_categories tool
    print("\nTesting list_factor_categories tool...")
    try:
        result = list_factor_categories.invoke({})
        print(f"✓ list_factor_categories result:\n{result[:200]}...")
    except Exception as e:
        print(f"✗ list_factor_categories failed: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("Factor Client & Tools Test")
    print("=" * 60)
    print("\nNote: These tests require the Go backend to be running")
    print("Start backend: cd go-backend && make run")
    print("=" * 60)

    # Test async client
    try:
        asyncio.run(test_client())
    except Exception as e:
        print(f"\n✗ Client tests failed: {e}")

    # Test sync tools
    try:
        test_tools()
    except Exception as e:
        print(f"\n✗ Tool tests failed: {e}")

    print("\n" + "=" * 60)
    print("Tests completed!")
    print("=" * 60)
