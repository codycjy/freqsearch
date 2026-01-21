#!/usr/bin/env python3
"""Import WorldQuant 101 Formulaic Alphas into FreqSearch Factor Database.

This script loads the WQ101 alpha factors, compiles their DSL expressions
into executable Python code, and imports them into the Factor API.

Usage:
    # Preview what will be imported (dry run)
    python scripts/import_wq101.py --dry-run

    # Import all factors
    python scripts/import_wq101.py

    # Force overwrite existing factors
    python scripts/import_wq101.py --force

    # Import with custom API URL
    python scripts/import_wq101.py --api-url http://localhost:8083/api/v1

Requirements:
    - Go backend must be running (default: http://localhost:8083)
    - PostgreSQL database must be accessible
    - Python environment: conda activate freq

Examples:
    # Standard import
    conda run -n freq python scripts/import_wq101.py

    # Preview without importing
    conda run -n freq python scripts/import_wq101.py --dry-run

    # Force reimport all factors
    conda run -n freq python scripts/import_wq101.py --force
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

# Add python-agents/src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "python-agents" / "src"))

import structlog

from freqsearch_agents.factors.client import FactorClient, FactorClientError
from freqsearch_agents.factors.compiler import FactorCompiler
from freqsearch_agents.factors.wq101_data import WQ101_FACTORS

logger = structlog.get_logger(__name__)


class ImportStats:
    """Track import statistics."""

    def __init__(self) -> None:
        self.success: int = 0
        self.failed: int = 0
        self.skipped: int = 0
        self.total: int = 0
        self.errors: list[dict[str, Any]] = []

    def add_success(self) -> None:
        """Record successful import."""
        self.success += 1

    def add_failed(self, name: str, error: str) -> None:
        """Record failed import."""
        self.failed += 1
        self.errors.append({"name": name, "error": error})

    def add_skipped(self, name: str, reason: str = "already exists") -> None:
        """Record skipped import."""
        self.skipped += 1
        self.errors.append({"name": name, "reason": reason})

    def print_summary(self) -> None:
        """Print import summary."""
        print("\n" + "=" * 70)
        print("IMPORT SUMMARY")
        print("=" * 70)
        print(f"Total factors:   {self.total}")
        print(f"Imported:        {self.success} ✓")
        print(f"Skipped:         {self.skipped} ⊘")
        print(f"Failed:          {self.failed} ✗")
        print("=" * 70)

        if self.errors and self.failed > 0:
            print("\nERRORS:")
            for err in self.errors:
                if "error" in err:
                    print(f"  • {err['name']}: {err['error']}")

        if self.skipped > 0:
            print(f"\nNote: {self.skipped} factors already exist (use --force to overwrite)")


async def compile_factor(
    compiler: FactorCompiler,
    factor: dict[str, Any],
) -> dict[str, Any] | None:
    """Compile a factor's DSL expression to Python code.

    Args:
        compiler: FactorCompiler instance
        factor: Factor dictionary from WQ101_FACTORS

    Returns:
        Compiled code result or None if compilation failed
    """
    try:
        result = compiler.compile(
            name=factor["name"],
            expression=factor["expression"],
            description=factor["description"],
        )

        if not result["is_valid"]:
            logger.error(
                "Factor compilation failed",
                name=factor["name"],
                error=result.get("error"),
            )
            return None

        return result

    except Exception as e:
        logger.error("Compilation error", name=factor["name"], error=str(e))
        return None


async def build_factor_record(
    factor: dict[str, Any],
    compile_result: dict[str, Any],
) -> dict[str, Any]:
    """Build complete factor record for API submission.

    Args:
        factor: Original factor data from WQ101_FACTORS
        compile_result: Compilation result from FactorCompiler

    Returns:
        Complete factor record ready for API
    """
    return {
        # Identity
        "name": factor["name"],
        "source": factor["source"],
        "version": 1,
        # Expression & Code
        "expression": factor["expression"],
        "description": factor["description"],
        "code_template": compile_result["code"],
        # Dependencies
        "operator_deps": compile_result["operator_deps"],
        "data_deps": compile_result["data_deps"],
        # 6-Dimension Classification
        "category": factor["category"],
        "signal_type": factor["signal_type"],
        "holding_period": factor["holding_period"],
        "data_requirement": factor["data_requirement"],
        "market_regime": factor["market_regime"],
        "complexity": factor["complexity"],
        # Status
        "is_active": True,
    }


async def import_factor(
    client: FactorClient,
    factor: dict[str, Any],
    force: bool = False,
    dry_run: bool = False,
) -> tuple[bool, str]:
    """Import a single factor.

    Args:
        client: FactorClient instance
        factor: Complete factor record
        force: Whether to overwrite existing factors
        dry_run: If True, only simulate import

    Returns:
        Tuple of (success, message)
    """
    name = factor["name"]

    if dry_run:
        return True, f"[DRY RUN] Would import: {name}"

    try:
        # Check if factor exists
        existing = await client.get_by_name(name)

        if existing and not force:
            return False, f"Factor '{name}' already exists (use --force to overwrite)"

        # Create or update factor
        await client.create(factor)
        return True, f"Imported: {name}"

    except FactorClientError as e:
        if "already exists" in str(e).lower() and not force:
            return False, f"Factor '{name}' already exists"
        return False, f"API error for '{name}': {str(e)}"

    except Exception as e:
        return False, f"Unexpected error for '{name}': {str(e)}"


async def import_all_factors(
    api_url: str | None = None,
    dry_run: bool = False,
    force: bool = False,
    verbose: bool = False,
) -> ImportStats:
    """Import all WQ101 factors into the database.

    Args:
        api_url: Custom API URL (default: http://localhost:8083/api/v1)
        dry_run: If True, simulate import without making changes
        force: If True, overwrite existing factors
        verbose: If True, show detailed progress

    Returns:
        ImportStats with import results
    """
    stats = ImportStats()
    stats.total = len(WQ101_FACTORS)

    # Initialize compiler and client
    compiler = FactorCompiler()

    client_kwargs = {}
    if api_url:
        client_kwargs["base_url"] = api_url

    async with FactorClient(**client_kwargs) as client:
        logger.info(
            "Starting WQ101 import",
            total_factors=stats.total,
            dry_run=dry_run,
            force=force,
        )

        if dry_run:
            print(f"\n{'=' * 70}")
            print("DRY RUN MODE - No changes will be made")
            print(f"{'=' * 70}\n")

        # Process each factor
        for idx, factor in enumerate(WQ101_FACTORS, 1):
            name = factor["name"]

            if verbose or dry_run:
                print(f"[{idx}/{stats.total}] Processing {name}...")

            # Step 1: Compile expression
            compile_result = await compile_factor(compiler, factor)

            if compile_result is None:
                stats.add_failed(name, "Compilation failed")
                print(f"  ✗ Compilation failed: {name}")
                continue

            # Step 2: Build complete record
            try:
                record = await build_factor_record(factor, compile_result)
            except Exception as e:
                stats.add_failed(name, f"Record building failed: {str(e)}")
                print(f"  ✗ Build failed: {name}")
                continue

            # Step 3: Import to API
            success, message = await import_factor(client, record, force, dry_run)

            if success:
                stats.add_success()
                if verbose or dry_run:
                    print(f"  ✓ {message}")
            else:
                if "already exists" in message:
                    stats.add_skipped(name)
                    if verbose:
                        print(f"  ⊘ {message}")
                else:
                    stats.add_failed(name, message)
                    print(f"  ✗ {message}")

    return stats


def setup_logging(verbose: bool = False) -> None:
    """Configure structured logging.

    Args:
        verbose: If True, enable debug logging
    """
    import logging
    log_level = logging.DEBUG if verbose else logging.INFO

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )


async def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(
        description="Import WorldQuant 101 Formulaic Alphas into FreqSearch",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview import (dry run)
  python scripts/import_wq101.py --dry-run

  # Import all factors
  python scripts/import_wq101.py

  # Force overwrite existing factors
  python scripts/import_wq101.py --force

  # Use custom API URL
  python scripts/import_wq101.py --api-url http://localhost:8083/api/v1
        """,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview import without making changes",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing factors",
    )

    parser.add_argument(
        "--api-url",
        type=str,
        help="Factor API base URL (default: from config or http://localhost:8083/api/v1)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)

    # Print header
    print("\n" + "=" * 70)
    print("WorldQuant 101 Formulaic Alphas - Import Tool")
    print("=" * 70)
    print(f"Total factors: {len(WQ101_FACTORS)}")
    if args.api_url:
        print(f"API URL: {args.api_url}")
    if args.dry_run:
        print("Mode: DRY RUN (simulation only)")
    if args.force:
        print("Mode: FORCE (overwrite existing)")
    print("=" * 70 + "\n")

    # Run import
    try:
        stats = await import_all_factors(
            api_url=args.api_url,
            dry_run=args.dry_run,
            force=args.force,
            verbose=args.verbose,
        )

        # Print summary
        stats.print_summary()

        # Return exit code
        if stats.failed > 0:
            print("\n⚠ Some factors failed to import. Check errors above.")
            return 1

        if stats.success == 0 and not args.dry_run:
            print("\n⚠ No factors were imported.")
            return 1

        print(f"\n✓ Import completed successfully!")
        return 0

    except KeyboardInterrupt:
        print("\n\n⚠ Import cancelled by user")
        return 130

    except Exception as e:
        logger.error("Import failed with unexpected error", error=str(e))
        print(f"\n✗ FATAL ERROR: {str(e)}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
