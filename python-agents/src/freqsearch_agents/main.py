"""FreqSearch Agents CLI and entry points."""


import asyncio
import logging
from typing import Optional, Any

import typer
from rich.console import Console
from rich.table import Table
import structlog

from .config import get_settings
from .agents.scout import run_scout
from .agents.engineer import run_engineer
from .agents.analyst import run_analyst
from .core.messaging import message_broker, Events, publish_event

# Configure standard library logging level
logging.basicConfig(
    format="%(message)s",
    level=logging.INFO,
)

# Configure structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

app = typer.Typer(
    name="freqsearch-agents",
    help="FreqSearch AI Agents for strategy discovery and optimization",
)
console = Console()


@app.command()
def scout(
    source: str = typer.Option("stratninja", help="Strategy source to use"),
    limit: int = typer.Option(20, help="Maximum strategies to fetch"),
):
    """Run the Scout Agent to discover new strategies."""
    console.print(f"[bold blue]Starting Scout Agent[/bold blue]")
    console.print(f"Source: {source}, Limit: {limit}")

    async def _run():
        async with message_broker():
            result = await run_scout(source=source, limit=limit)
            return result

    result = asyncio.run(_run())

    # Display results
    table = Table(title="Scout Agent Results")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Total Fetched", str(result["total_fetched"]))
    table.add_row("Validation Failed", str(result["validation_failed"]))
    table.add_row("Duplicates Removed", str(result["duplicates_removed"]))
    table.add_row("Submitted", str(result["submitted_count"]))

    if result["errors"]:
        table.add_row("Errors", str(len(result["errors"])))

    console.print(table)


@app.command()
def engineer(
    strategy_file: str = typer.Argument(..., help="Path to strategy Python file"),
    mode: str = typer.Option("new", help="Processing mode: new, fix, evolve"),
    max_retries: int = typer.Option(3, help="Maximum retry attempts"),
):
    """Run the Engineer Agent to process a strategy."""
    console.print(f"[bold blue]Starting Engineer Agent[/bold blue]")
    console.print(f"File: {strategy_file}, Mode: {mode}")

    # Read strategy file
    try:
        with open(strategy_file, "r") as f:
            code = f.read()
    except FileNotFoundError:
        console.print(f"[red]File not found: {strategy_file}[/red]")
        raise typer.Exit(1)

    input_data = {
        "name": strategy_file.split("/")[-1].replace(".py", ""),
        "code": code,
    }

    async def _run():
        async with message_broker():
            result = await run_engineer(
                input_data=input_data,
                mode=mode,
                max_retries=max_retries,
            )
            return result

    result = asyncio.run(_run())

    # Display results
    if result["validation_passed"]:
        console.print("[green]Strategy processed successfully![/green]")
        console.print(f"Retry count: {result['retry_count']}")

        if result["hyperopt_config"]:
            console.print("\n[bold]Hyperopt Configuration:[/bold]")
            params = result["hyperopt_config"].get("existing_parameters", [])
            if params:
                for p in params:
                    console.print(f"  - {p['name']}: {p.get('low', '?')} - {p.get('high', '?')}")
    else:
        console.print("[red]Strategy processing failed[/red]")
        for error in result["validation_errors"]:
            console.print(f"  - {error}")


@app.command()
def analyze(
    result_file: str = typer.Argument(..., help="Path to backtest result JSON"),
    strategy_file: Optional[str] = typer.Option(None, help="Optional strategy file"),
):
    """Run the Analyst Agent to analyze backtest results."""
    import json

    console.print(f"[bold blue]Starting Analyst Agent[/bold blue]")

    # Load result file
    try:
        with open(result_file, "r") as f:
            backtest_result = json.load(f)
    except FileNotFoundError:
        console.print(f"[red]File not found: {result_file}[/red]")
        raise typer.Exit(1)

    # Optionally load strategy code
    strategy_code = None
    if strategy_file:
        try:
            with open(strategy_file, "r") as f:
                strategy_code = f.read()
        except FileNotFoundError:
            console.print(f"[yellow]Strategy file not found, continuing without[/yellow]")

    async def _run():
        async with message_broker():
            result = await run_analyst(
                backtest_result=backtest_result,
                strategy_code=strategy_code,
            )
            return result

    result = asyncio.run(_run())

    # Display results
    table = Table(title="Analyst Agent Results")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Decision", result["decision"])
    table.add_row("Confidence", f"{result['confidence']:.1%}")

    if result["issues"]:
        table.add_row("Issues", "\n".join(result["issues"]))

    if result["suggestion_type"]:
        table.add_row("Suggestion Type", result["suggestion_type"])
        table.add_row("Suggestion", result["suggestion_description"] or "N/A")

    console.print(table)


@app.command()
def serve(
    scout_enabled: bool = typer.Option(True, help="Enable Scout Agent"),
    engineer_enabled: bool = typer.Option(True, help="Enable Engineer Agent"),
    analyst_enabled: bool = typer.Option(True, help="Enable Analyst Agent"),
    heartbeat_interval: int = typer.Option(15, help="Heartbeat interval in seconds"),
):
    """Start agents as message queue consumers."""
    from .core.messaging import Events, get_broker

    console.print("[bold blue]Starting Agent Service[/bold blue]")
    console.print(f"Scout: {scout_enabled}, Engineer: {engineer_enabled}, Analyst: {analyst_enabled}")
    console.print(f"Heartbeat interval: {heartbeat_interval}s")

    # Track current task for each agent
    agent_tasks: dict[str, str | None] = {
        "orchestrator": None,
        "engineer": None,
        "analyst": None,
        "scout": None,
    }

    async def heartbeat_task(agent_type: str):
        """Send periodic heartbeat for an agent."""
        while True:
            current_task = agent_tasks.get(agent_type)
            status = "active" if current_task else "idle"
            await publish_event(
                Events.AGENT_HEARTBEAT,
                {
                    "agent_type": agent_type,
                    "status": status,
                    "current_task": current_task or "",
                },
            )
            await asyncio.sleep(heartbeat_interval)

    async def _serve():
        broker = get_broker()
        await broker.connect()

        tasks = []

        # Start heartbeat tasks for enabled agents
        if engineer_enabled:
            tasks.append(asyncio.create_task(heartbeat_task("engineer")))

            # Subscribe to strategy.needs_processing
            async def handle_strategy_needs_processing(data):
                agent_tasks["engineer"] = f"Processing: {data.get('name', 'unknown')}"
                console.print(f"[cyan]Processing strategy: {data.get('name')}[/cyan]")
                try:
                    await run_engineer(input_data=data, mode="new")
                finally:
                    agent_tasks["engineer"] = None

            tasks.append(
                asyncio.create_task(
                    broker.subscribe(
                        Events.STRATEGY_NEEDS_PROCESSING,
                        "engineer-queue",
                        handle_strategy_needs_processing,
                    )
                )
            )

            # Subscribe to strategy.evolve
            async def handle_strategy_evolve(data):
                agent_tasks["engineer"] = f"Evolving: {data.get('strategy_name', 'unknown')}"
                console.print(f"[cyan]Evolving strategy: {data.get('strategy_name')}[/cyan]")
                try:
                    await run_engineer(input_data=data, mode="evolve")
                finally:
                    agent_tasks["engineer"] = None

            tasks.append(
                asyncio.create_task(
                    broker.subscribe(
                        Events.STRATEGY_EVOLVE,
                        "engineer-evolve-queue",
                        handle_strategy_evolve,
                    )
                )
            )

        if analyst_enabled:
            tasks.append(asyncio.create_task(heartbeat_task("analyst")))

            # Subscribe to backtest.completed
            async def handle_backtest_completed(data):
                agent_tasks["analyst"] = f"Analyzing: {data.get('job_id', 'unknown')}"
                console.print(f"[cyan]Analyzing backtest: {data.get('job_id')}[/cyan]")
                try:
                    await run_analyst(backtest_result=data)
                finally:
                    agent_tasks["analyst"] = None

            tasks.append(
                asyncio.create_task(
                    broker.subscribe(
                        Events.BACKTEST_COMPLETED,
                        "analyst-queue",
                        handle_backtest_completed,
                    )
                )
            )

        if scout_enabled:
            tasks.append(asyncio.create_task(heartbeat_task("scout")))

            # Subscribe to scout.trigger
            async def handle_scout_trigger(data):
                run_id = data.get("run_id")
                source = data.get("source", "stratninja")
                max_strategies = data.get("max_strategies", 50)

                agent_tasks["scout"] = f"Scout: {source} (run: {run_id})"
                console.print(f"[cyan]Scout triggered: {source}, limit: {max_strategies}, run_id: {run_id}[/cyan]")
                try:
                    await run_scout(source=source, limit=max_strategies, run_id=run_id)
                except Exception as e:
                    logger.error("Scout run failed", error=str(e), run_id=run_id)
                finally:
                    agent_tasks["scout"] = None

            tasks.append(
                asyncio.create_task(
                    broker.subscribe(
                        Events.SCOUT_TRIGGER,
                        "scout-trigger-queue",
                        handle_scout_trigger,
                    )
                )
            )

        # Always start orchestrator heartbeat
        tasks.append(asyncio.create_task(heartbeat_task("orchestrator")))

        console.print("[green]Agent service started. Press Ctrl+C to stop.[/green]")

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass
        finally:
            await broker.disconnect()

    try:
        asyncio.run(_serve())
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down...[/yellow]")


@app.command()
def config():
    """Show current configuration."""
    settings = get_settings()

    table = Table(title="FreqSearch Agents Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("OpenAI Model", settings.openai.model)
    table.add_row("Database URL", settings.database.url[:50] + "...")
    table.add_row("RabbitMQ URL", settings.rabbitmq.url)
    table.add_row("Go Backend gRPC", settings.grpc.go_backend_addr)
    table.add_row("Scout Schedule", settings.scout.cron_schedule)
    table.add_row("Scout Max Strategies", str(settings.scout.max_strategies_per_run))
    table.add_row("Engineer Max Retries", str(settings.engineer.max_retries))
    table.add_row("Analyst Confidence Threshold", str(settings.analyst.confidence_threshold))

    console.print(table)


if __name__ == "__main__":
    app()
