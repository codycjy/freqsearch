#!/usr/bin/env python3
"""
Example usage of the improved SimHash deduplication system.

This example demonstrates how to use both SimHash (for similarity)
and SHA256 (for exact matching) to deduplicate trading strategies.
"""

from freqsearch_agents.tools.code.simhash import (
    compute_code_hash,
    compute_sha256_hash,
    is_duplicate_code,
    deduplicate_strategies,
    DEFAULT_SIMHASH_THRESHOLD,
)


def example_basic_usage():
    """Basic usage example."""
    print("=" * 70)
    print("BASIC USAGE EXAMPLE")
    print("=" * 70)

    code1 = """
def populate_indicators(dataframe, metadata):
    # Calculate EMA
    dataframe['ema_fast'] = ta.EMA(dataframe, timeperiod=12)
    dataframe['ema_slow'] = ta.EMA(dataframe, timeperiod=26)
    return dataframe
"""

    code2 = """
def populate_indicators(dataframe, metadata):
    # Different comment
    dataframe['ema_fast'] = ta.EMA(dataframe, timeperiod=12)
    dataframe['ema_slow'] = ta.EMA(dataframe, timeperiod=26)
    return dataframe
"""

    # Compute hashes
    simhash1 = compute_code_hash(code1)
    simhash2 = compute_code_hash(code2)
    sha256_1 = compute_sha256_hash(code1)
    sha256_2 = compute_sha256_hash(code2)

    print(f"\nCode 1 SimHash: {simhash1}")
    print(f"Code 2 SimHash: {simhash2}")
    print(f"\nCode 1 SHA256: {sha256_1}")
    print(f"Code 2 SHA256: {sha256_2}")

    print(f"\nAre they duplicates (SimHash)? {is_duplicate_code(simhash1, simhash2)}")
    print(f"Are they exact matches (SHA256)? {sha256_1 == sha256_2}")

    print("\n✓ Same code with different comments = exact match!\n")


def example_strategy_deduplication():
    """Example of deduplicating a list of strategies."""
    print("=" * 70)
    print("STRATEGY DEDUPLICATION EXAMPLE")
    print("=" * 70)

    strategies = [
        {
            "name": "EMA_Crossover_v1",
            "code": "def entry(): return df['ema_fast'] > df['ema_slow']",
            "code_hash": None,
        },
        {
            "name": "EMA_Crossover_v2",
            "code": "def entry():\n    # With comment\n    return df['ema_fast'] > df['ema_slow']",
            "code_hash": None,
        },
        {
            "name": "RSI_Strategy",
            "code": "def entry(): return df['rsi'] < 30",
            "code_hash": None,
        },
        {
            "name": "EMA_Crossover_v3",
            "code": "def entry(): return df['ema_fast'] > df['ema_slow']",
            "code_hash": None,
        },
    ]

    # Compute hashes
    for strategy in strategies:
        strategy['code_hash'] = compute_code_hash(strategy['code'])

    print(f"\nProcessing {len(strategies)} strategies...")

    # Deduplicate
    unique, duplicates = deduplicate_strategies(
        strategies,
        hash_field='code_hash',
        id_field='name',
        threshold=DEFAULT_SIMHASH_THRESHOLD,
    )

    print(f"\nResults:")
    print(f"  Unique strategies: {len(unique)}")
    print(f"  Duplicate strategies: {len(duplicates)}")

    print(f"\nUnique strategies:")
    for s in unique:
        print(f"  - {s['name']}")

    print(f"\nDuplicate strategies (filtered out):")
    for s in duplicates:
        print(f"  - {s['name']}")

    print("\n✓ Deduplication complete!\n")


def example_database_check():
    """Example of checking against existing database entries."""
    print("=" * 70)
    print("DATABASE DEDUPLICATION EXAMPLE")
    print("=" * 70)

    # Simulate existing strategies in database
    database_strategies = [
        {
            "id": 1,
            "name": "Existing_Strategy_1",
            "sha256": "abc123...",
            "simhash": "fedcba...",
        },
        {
            "id": 2,
            "name": "Existing_Strategy_2",
            "sha256": "def456...",
            "simhash": "123456...",
        },
    ]

    new_code = """
def populate_indicators(dataframe, metadata):
    dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
    return dataframe
"""

    # Compute hashes for new code
    new_sha256 = compute_sha256_hash(new_code)
    new_simhash = compute_code_hash(new_code)

    print(f"\nNew strategy hashes:")
    print(f"  SHA256:  {new_sha256}")
    print(f"  SimHash: {new_simhash}")

    # Check for exact duplicates (fast)
    print(f"\nStep 1: Check for exact duplicates (SHA256)")
    exact_duplicate = None
    for existing in database_strategies:
        if existing['sha256'] == new_sha256:
            exact_duplicate = existing
            break

    if exact_duplicate:
        print(f"  ✗ Exact duplicate found: {exact_duplicate['name']}")
        print(f"    Action: Skip this strategy")
        return

    print(f"  ✓ No exact duplicates found")

    # Check for similar strategies (slower)
    print(f"\nStep 2: Check for similar strategies (SimHash)")
    similar_strategies = []
    for existing in database_strategies:
        if is_duplicate_code(new_simhash, existing['simhash']):
            similar_strategies.append(existing)

    if similar_strategies:
        print(f"  ⚠ Similar strategies found:")
        for s in similar_strategies:
            print(f"    - {s['name']}")
        print(f"    Action: Review manually or apply stricter threshold")
    else:
        print(f"  ✓ No similar strategies found")
        print(f"    Action: Add to database")

    print("\n✓ Database check complete!\n")


def example_cross_batch_deduplication():
    """Example of cross-batch deduplication using SHA256."""
    print("=" * 70)
    print("CROSS-BATCH DEDUPLICATION EXAMPLE")
    print("=" * 70)

    # Simulate multiple scout runs
    batch1_strategies = [
        "def entry(): return df['rsi'] < 30",
        "def entry(): return df['ema_fast'] > df['ema_slow']",
    ]

    batch2_strategies = [
        "def entry():\n    # Comment\n    return df['rsi'] < 30",  # Same as batch1[0]
        "def entry(): return df['macd'] > 0",  # New
    ]

    print("\nBatch 1 (2 strategies)")
    print("Batch 2 (2 strategies)")

    # Create SHA256 index from batch 1
    sha256_index = set()
    for code in batch1_strategies:
        sha256_index.add(compute_sha256_hash(code))

    print(f"\nSHA256 index built: {len(sha256_index)} unique strategies")

    # Check batch 2 against index
    print(f"\nChecking batch 2 strategies:")
    new_strategies = 0
    duplicate_strategies = 0

    for i, code in enumerate(batch2_strategies, 1):
        sha256 = compute_sha256_hash(code)
        if sha256 in sha256_index:
            print(f"  Strategy {i}: DUPLICATE (skip)")
            duplicate_strategies += 1
        else:
            print(f"  Strategy {i}: NEW (add to index)")
            sha256_index.add(sha256)
            new_strategies += 1

    print(f"\nResults:")
    print(f"  New strategies: {new_strategies}")
    print(f"  Duplicate strategies: {duplicate_strategies}")
    print(f"  Total unique strategies: {len(sha256_index)}")

    print("\n✓ Cross-batch deduplication complete!\n")


def main():
    """Run all examples."""
    print("\n" + "█" * 70)
    print("█  SIMHASH DEDUPLICATION SYSTEM - USAGE EXAMPLES" + " " * 21 + "█")
    print("█" * 70 + "\n")

    example_basic_usage()
    example_strategy_deduplication()
    example_database_check()
    example_cross_batch_deduplication()

    print("█" * 70)
    print("█  ALL EXAMPLES COMPLETED" + " " * 44 + "█")
    print("█" * 70 + "\n")


if __name__ == "__main__":
    main()
