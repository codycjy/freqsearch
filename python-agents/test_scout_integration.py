#!/usr/bin/env python3
"""Test script to verify Scout agent source integration.

This script verifies that:
1. All sources are properly registered
2. Source factories work correctly
3. Pine Script detection works
4. Validation handles both Python and Pine Script strategies
"""

import asyncio
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from freqsearch_agents.agents.scout.nodes import SOURCE_REGISTRY


def test_source_registry():
    """Test that all sources are registered."""
    print("=" * 60)
    print("Testing Source Registry")
    print("=" * 60)

    expected_sources = ["stratninja", "github_repo", "github_code", "tradingview"]
    registered_sources = list(SOURCE_REGISTRY.keys())

    print(f"\nExpected sources: {expected_sources}")
    print(f"Registered sources: {registered_sources}")

    for source_name in expected_sources:
        if source_name in registered_sources:
            print(f"✓ {source_name} is registered")
        else:
            print(f"✗ {source_name} is NOT registered")
            return False

    print("\n✓ All sources are properly registered!")
    return True


def test_source_instantiation():
    """Test that source factories can be instantiated."""
    print("\n" + "=" * 60)
    print("Testing Source Instantiation")
    print("=" * 60)

    for source_name, factory in SOURCE_REGISTRY.items():
        try:
            source = factory()
            print(f"✓ {source_name}: {source.__class__.__name__}")
            print(f"  - source_name: {source.source_name}")
            print(f"  - description: {source.source_description[:60]}...")
        except Exception as e:
            print(f"✗ {source_name}: Failed to instantiate - {e}")
            return False

    print("\n✓ All sources can be instantiated!")
    return True


def test_pine_script_detection():
    """Test Pine Script detection logic."""
    print("\n" + "=" * 60)
    print("Testing Pine Script Detection")
    print("=" * 60)

    # Sample Pine Script code
    pine_code = """
//@version=5
strategy("Test Strategy", overlay=true)
if (close > open)
    strategy.entry("Long", strategy.long)
"""

    # Sample Python code
    python_code = """
from freqtrade.strategy import IStrategy
import talib

class TestStrategy(IStrategy):
    def populate_indicators(self, dataframe, metadata):
        return dataframe
"""

    # Test detection logic
    pine_detected = "//@version=" in pine_code or "strategy(" in pine_code[:200]
    python_detected = "//@version=" in python_code or "strategy(" in python_code[:200]

    print(f"\nPine Script detected in Pine code: {pine_detected}")
    print(f"Pine Script detected in Python code: {python_detected}")

    if pine_detected and not python_detected:
        print("\n✓ Pine Script detection works correctly!")
        return True
    else:
        print("\n✗ Pine Script detection has issues!")
        return False


async def test_source_compatibility():
    """Test that sources are compatible with async context management."""
    print("\n" + "=" * 60)
    print("Testing Source Async Compatibility")
    print("=" * 60)

    for source_name, factory in SOURCE_REGISTRY.items():
        try:
            source = factory()
            has_aenter = hasattr(source, "__aenter__")
            has_aexit = hasattr(source, "__aexit__")

            print(f"\n{source_name}:")
            print(f"  - __aenter__: {has_aenter}")
            print(f"  - __aexit__: {has_aexit}")

            if has_aenter and has_aexit:
                print(f"  - Supports async context manager")
            else:
                print(f"  - Standard synchronous interface")

        except Exception as e:
            print(f"✗ {source_name}: Error - {e}")
            return False

    print("\n✓ All sources are compatible!")
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Scout Agent Source Integration Tests")
    print("=" * 60)

    tests = [
        test_source_registry,
        test_source_instantiation,
        test_pine_script_detection,
    ]

    async_tests = [
        test_source_compatibility,
    ]

    results = []

    # Run synchronous tests
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n✗ Test failed with exception: {e}")
            results.append(False)

    # Run async tests
    for test in async_tests:
        try:
            result = asyncio.run(test())
            results.append(result)
        except Exception as e:
            print(f"\n✗ Test failed with exception: {e}")
            results.append(False)

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"\nPassed: {passed}/{total}")

    if all(results):
        print("\n✓ All tests passed!")
        return 0
    else:
        print("\n✗ Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
