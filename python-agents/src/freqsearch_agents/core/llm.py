"""OpenAI LLM and Embeddings client wrappers."""

from functools import lru_cache

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from ..config import get_settings


@lru_cache
def get_llm() -> ChatOpenAI:
    """Get cached LLM instance."""
    settings = get_settings()
    return ChatOpenAI(
        api_key=settings.openai.api_key,
        model=settings.openai.model,
        temperature=settings.openai.temperature,
        max_tokens=settings.openai.max_tokens,
    )


@lru_cache
def get_embeddings() -> OpenAIEmbeddings:
    """Get cached embeddings instance."""
    settings = get_settings()
    return OpenAIEmbeddings(
        api_key=settings.openai.api_key,
        model=settings.openai.embedding_model,
    )


def get_llm_with_structured_output(output_schema: type):
    """Get LLM configured for structured output.

    Args:
        output_schema: Pydantic model class for output structure

    Returns:
        LLM bound to the output schema
    """
    llm = get_llm()
    return llm.with_structured_output(output_schema)
