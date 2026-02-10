"""LLM client wrappers with per-agent model support. Supports OpenRouter and Azure OpenAI."""

from functools import lru_cache
from typing import Literal

from langchain_openai import AzureChatOpenAI, ChatOpenAI, OpenAIEmbeddings

from ..config import get_settings

AgentType = Literal["scout", "engineer", "analyst"]


def _create_llm(model: str, temperature: float, max_tokens: int) -> ChatOpenAI | AzureChatOpenAI:
    """Create LLM instance based on provider setting."""
    settings = get_settings()
    llm_settings = settings.llm

    if llm_settings.provider == "azure":
        return AzureChatOpenAI(
            azure_deployment=model,
            api_version=llm_settings.azure_api_version,
            # temperature=temperature, # gpt does not accept temperature
            max_tokens=max_tokens,
        )

    # Default: OpenRouter
    return ChatOpenAI(
        api_key=llm_settings.openrouter_api_key,
        base_url="https://openrouter.ai/api/v1",
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def get_llm_for_agent(agent_type: AgentType) -> ChatOpenAI | AzureChatOpenAI:
    """Get LLM instance configured for specific agent."""
    settings = get_settings()
    llm_settings = settings.llm

    model_map = {
        "scout": llm_settings.scout_model,
        "engineer": llm_settings.engineer_model,
        "analyst": llm_settings.analyst_model,
    }
    model = model_map.get(agent_type, llm_settings.default_model)

    return _create_llm(model, llm_settings.temperature, llm_settings.max_tokens)


@lru_cache
def get_llm() -> ChatOpenAI | AzureChatOpenAI:
    """Get cached default LLM instance (uses default model)."""
    settings = get_settings()
    llm_settings = settings.llm

    return _create_llm(llm_settings.default_model, llm_settings.temperature, llm_settings.max_tokens)


@lru_cache
def get_embeddings() -> OpenAIEmbeddings:
    """Get cached embeddings instance (still uses OpenAI)."""
    settings = get_settings()
    return OpenAIEmbeddings(
        api_key=settings.openai.api_key,
        model=settings.llm.embedding_model,
    )


def get_llm_with_structured_output(output_schema: type, agent_type: AgentType | None = None):
    """Get LLM configured for structured output."""
    if agent_type:
        llm = get_llm_for_agent(agent_type)
    else:
        llm = get_llm()
    return llm.with_structured_output(output_schema)
