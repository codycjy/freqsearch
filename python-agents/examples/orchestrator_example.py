#!/usr/bin/env python3
"""Example: Running the Orchestrator Agent for strategy optimization.

This example demonstrates:
1. Basic orchestrator usage
2. Streaming mode for real-time monitoring
3. Event subscription for monitoring
4. Error handling and retry logic
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from freqsearch_agents.agents.orchestrator import run_orchestrator, run_orchestrator_streaming
from freqsearch_agents.core.messaging import get_broker
import structlog

logger = structlog.get_logger(__name__)


async def example_basic_run():
    """Example 1: Basic orchestrator run."""
    print("\n" + "=" * 60)
    print("EXAMPLE 1: Basic Orchestrator Run")
    print("=" * 60 + "\n")

    result = await run_orchestrator(
        optimization_run_id="example_opt_001",
        base_strategy_id="example_strategy_base",
        max_iterations=5,
    )

    print("\nOptimization Results:")
    print(f"  Terminated: {result['terminated']}")
    print(f"  Reason: {result['termination_reason']}")
    print(f"  Total Iterations: {result['current_iteration'] + 1}")
    print(f"  Best Strategy: {result['best_strategy_id']}")
    print(f"  Best Sharpe Ratio: {result['best_sharpe']:.2f}")

    if result["best_result"]:
        print(f"\nBest Strategy Performance:")
        print(f"  Profit: {result['best_result'].get('profit_pct', 0):.2f}%")
        print(f"  Win Rate: {result['best_result'].get('win_rate', 0):.2%}")
        print(f"  Max Drawdown: {result['best_result'].get('max_drawdown_pct', 0):.2f}%")

    if result.get("errors"):
        print(f"\nErrors encountered:")
        for error in result["errors"]:
            print(f"  - {error}")

    return result


async def example_streaming_run():
    """Example 2: Streaming mode with real-time updates."""
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Streaming Mode")
    print("=" * 60 + "\n")

    print("Starting optimization with streaming updates...\n")

    current_iteration = 0
    best_sharpe = float("-inf")

    async for update in run_orchestrator_streaming(
        optimization_run_id="example_opt_002",
        base_strategy_id="example_strategy_base",
        max_iterations=3,
    ):
        # Extract node name and state
        node_name = list(update.keys())[0]
        state = update[node_name]

        # Track iteration changes
        iteration = state.get("current_iteration", 0)
        if iteration != current_iteration:
            current_iteration = iteration
            print(f"\n--- Iteration {iteration + 1} ---")

        # Display node execution
        print(f"  → {node_name}")

        # Show key state changes
        if node_name == "invoke_engineer":
            strategy_id = state.get("current_strategy_id", "N/A")
            print(f"    Generated: {strategy_id}")

        elif node_name == "submit_backtest":
            job_id = state.get("current_backtest_job_id", "N/A")
            print(f"    Job ID: {job_id}")

        elif node_name == "wait_for_result":
            result = state.get("current_result", {})
            if result:
                sharpe = result.get("sharpe_ratio", 0)
                print(f"    Sharpe: {sharpe:.2f}")

        elif node_name == "invoke_analyst":
            decision = state.get("analyst_decision", "N/A")
            print(f"    Decision: {decision}")

        elif node_name == "process_decision":
            new_best = state.get("best_sharpe", float("-inf"))
            if new_best > best_sharpe:
                best_sharpe = new_best
                print(f"    ★ New best! Sharpe: {best_sharpe:.2f}")

        elif node_name == "complete":
            print("\n✓ Optimization completed!")
            print(f"  Best Strategy: {state.get('best_strategy_id', 'N/A')}")
            print(f"  Best Sharpe: {state.get('best_sharpe', 0):.2f}")

        elif node_name == "handle_failure":
            print("\n✗ Optimization failed!")
            errors = state.get("errors", [])
            for error in errors:
                print(f"  Error: {error}")


async def example_event_monitoring():
    """Example 3: Monitor optimization via RabbitMQ events."""
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Event Monitoring")
    print("=" * 60 + "\n")

    # Event handler
    async def handle_optimization_event(event_data: dict):
        event_type = event_data.get("event_type", "unknown")

        if "iteration.started" in str(event_data):
            iteration = event_data.get("iteration", 0)
            print(f"[EVENT] Iteration {iteration + 1} started")

        elif "new_best" in str(event_data):
            sharpe = event_data.get("sharpe_ratio", 0)
            print(f"[EVENT] ★ New best strategy! Sharpe: {sharpe:.2f}")

        elif "iteration.completed" in str(event_data):
            iteration = event_data.get("iteration", 0)
            decision = event_data.get("decision", "N/A")
            print(f"[EVENT] Iteration {iteration + 1} completed - Decision: {decision}")

        elif "completed" in str(event_data):
            total = event_data.get("total_iterations", 0)
            best_sharpe = event_data.get("best_sharpe", 0)
            print(f"[EVENT] ✓ Optimization completed! Total: {total}, Best Sharpe: {best_sharpe:.2f}")

        elif "failed" in str(event_data):
            reason = event_data.get("reason", "unknown")
            print(f"[EVENT] ✗ Optimization failed: {reason}")

    # Subscribe to events
    broker = get_broker()
    await broker.connect()

    # Create subscription task
    subscription_task = asyncio.create_task(
        broker.subscribe(
            routing_key="optimization.*",
            queue_name="example_monitor",
            handler=handle_optimization_event,
        )
    )

    # Give subscription time to set up
    await asyncio.sleep(1)

    # Run optimization in background
    print("Starting optimization (events will be displayed)...\n")

    optimization_task = asyncio.create_task(
        run_orchestrator(
            optimization_run_id="example_opt_003",
            base_strategy_id="example_strategy_base",
            max_iterations=3,
        )
    )

    # Wait for optimization to complete
    result = await optimization_task

    # Give time for final events to be processed
    await asyncio.sleep(2)

    # Cancel subscription
    subscription_task.cancel()
    try:
        await subscription_task
    except asyncio.CancelledError:
        pass

    await broker.disconnect()

    print("\nMonitoring complete!")
    return result


async def example_error_handling():
    """Example 4: Error handling and retry logic."""
    print("\n" + "=" * 60)
    print("EXAMPLE 4: Error Handling and Retry")
    print("=" * 60 + "\n")

    max_retries = 3

    for attempt in range(max_retries):
        print(f"Attempt {attempt + 1}/{max_retries}...")

        try:
            result = await run_orchestrator(
                optimization_run_id=f"example_opt_004_attempt_{attempt}",
                base_strategy_id="example_strategy_base",
                max_iterations=5,
            )

            # Check if successful
            if result["termination_reason"] in ["approved", "max_iterations_reached"]:
                print(f"\n✓ Success on attempt {attempt + 1}!")
                return result

            # Failed but can retry
            print(f"✗ Attempt {attempt + 1} did not produce good results")
            print(f"  Reason: {result['termination_reason']}")

            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"  Waiting {wait_time}s before retry...\n")
                await asyncio.sleep(wait_time)

        except Exception as e:
            print(f"✗ Attempt {attempt + 1} raised exception: {e}")

            if attempt == max_retries - 1:
                print("\n✗ Max retries exceeded, giving up")
                raise

            wait_time = 2 ** attempt
            print(f"  Waiting {wait_time}s before retry...\n")
            await asyncio.sleep(wait_time)

    print("\n✗ All attempts failed")
    return None


async def example_custom_configuration():
    """Example 5: Custom configuration options."""
    print("\n" + "=" * 60)
    print("EXAMPLE 5: Custom Configuration")
    print("=" * 60 + "\n")

    # Custom configuration
    config = {
        "poll_interval": 5.0,  # Poll every 5 seconds
        "max_wait_time": 3600.0,  # Max 1 hour wait
        "backtest_config": {
            "timerange": "20230101-20231231",
            "stake_amount": 100,
            "fee": 0.001,
        },
    }

    print("Configuration:")
    print(f"  Poll Interval: {config['poll_interval']}s")
    print(f"  Max Wait Time: {config['max_wait_time']}s")
    print(f"  Backtest Timerange: {config['backtest_config']['timerange']}")
    print()

    result = await run_orchestrator(
        optimization_run_id="example_opt_005",
        base_strategy_id="example_strategy_base",
        max_iterations=5,
        thread_id="custom-example-thread",  # Enable checkpointing
        config=config,
    )

    print(f"\nCompleted with custom config!")
    print(f"  Termination: {result['termination_reason']}")
    print(f"  Best Sharpe: {result['best_sharpe']:.2f}")

    return result


async def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("ORCHESTRATOR AGENT EXAMPLES")
    print("=" * 60)

    # Example 1: Basic run
    await example_basic_run()

    # Example 2: Streaming mode
    await example_streaming_run()

    # Example 3: Event monitoring
    # Uncomment if RabbitMQ is running:
    # await example_event_monitoring()

    # Example 4: Error handling
    # await example_error_handling()

    # Example 5: Custom configuration
    await example_custom_configuration()

    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    # Configure logging
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ]
    )

    # Run examples
    asyncio.run(main())
