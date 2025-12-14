"""Base agent utilities and shared components."""

from typing import Any

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

logger = structlog.get_logger(__name__)


def create_system_message(content: str) -> SystemMessage:
    """Create a system message for agent context."""
    return SystemMessage(content=content)


def create_human_message(content: str) -> HumanMessage:
    """Create a human message (task input)."""
    return HumanMessage(content=content)


def format_tool_result(result: Any) -> str:
    """Format a tool result for inclusion in messages."""
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        import json
        return json.dumps(result, indent=2, default=str)
    if isinstance(result, list):
        import json
        return json.dumps(result, indent=2, default=str)
    return str(result)
