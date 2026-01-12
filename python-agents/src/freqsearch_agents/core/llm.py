"""LLM client wrappers with per-agent model support via OpenRouter."""

from functools import lru_cache
from typing import Literal

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from ..config import get_settings

AgentType = Literal["scout", "engineer", "analyst"]


def get_llm_for_agent(agent_type: AgentType) -> ChatOpenAI:
    """Get LLM instance configured for specific agent.

    Args:
        agent_type: The agent type (scout, engineer, analyst)

    Returns:
        ChatOpenAI instance configured with the agent's model
    """
    settings = get_settings()
    llm_settings = settings.llm

    # Get model for this agent
    model_map = {
        "scout": llm_settings.scout_model,
        "engineer": llm_settings.engineer_model,
        "analyst": llm_settings.analyst_model,
    }
    model = model_map.get(agent_type, llm_settings.default_model)

    # Use OpenRouter API
    return ChatOpenAI(
        api_key=llm_settings.openrouter_api_key,
        base_url="https://openrouter.ai/api/v1",
        model=model,
        temperature=llm_settings.temperature,
        max_tokens=llm_settings.max_tokens,
    )


@lru_cache
def get_llm() -> ChatOpenAI:
    """Get cached default LLM instance (uses default model)."""
    settings = get_settings()
    llm_settings = settings.llm

    return ChatOpenAI(
        api_key=llm_settings.openrouter_api_key,
        base_url="https://openrouter.ai/api/v1",
        model=llm_settings.default_model,
        temperature=llm_settings.temperature,
        max_tokens=llm_settings.max_tokens,
    )


@lru_cache
def get_embeddings() -> OpenAIEmbeddings:
    """Get cached embeddings instance (still uses OpenAI)."""
    settings = get_settings()
    return OpenAIEmbeddings(
        api_key=settings.openai.api_key,
        model=settings.llm.embedding_model,
    )


def get_llm_with_structured_output(output_schema: type, agent_type: AgentType | None = None):
    """Get LLM configured for structured output.

    Args:
        output_schema: Pydantic model class for output structure
        agent_type: Optional agent type for model selection

    Returns:
        LLM bound to the output schema
    """
    if agent_type:
        llm = get_llm_for_agent(agent_type)
    else:
        llm = get_llm()
    return llm.with_structured_output(output_schema)
