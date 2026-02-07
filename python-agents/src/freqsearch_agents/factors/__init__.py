"""Factor library access for FreqSearch agents.

This module provides:
- 18 core operators for factor construction (operators.py)
- DSL compiler for WorldQuant-style expressions (compiler.py)
- HTTP client for accessing factor library (client.py)
- LangChain tools for agent integration (tools.py)
"""

from freqsearch_agents.factors.client import (
    FactorClient,
    FactorClientError,
    get_factor_client,
)
from freqsearch_agents.factors.compiler import FactorCompiler, compile_factor
from freqsearch_agents.factors.operators import (
    OPERATORS,
    abs_,
    correlation,
    covariance,
    decay_linear,
    delay,
    delta,
    log,
    product,
    rank,
    scale,
    sign,
    ts_argmax,
    ts_argmin,
    ts_max,
    ts_mean,
    ts_min,
    ts_rank,
    ts_std,
    ts_sum,
)
from freqsearch_agents.factors.tools import (
    get_factor_code,
    list_factor_categories,
    search_factors,
)

__all__ = [
    # Compiler
    "FactorCompiler",
    "compile_factor",
    # Operators registry
    "OPERATORS",
    # Time series operators
    "delay",
    "delta",
    "ts_sum",
    "ts_mean",
    "ts_std",
    "ts_rank",
    "ts_min",
    "ts_max",
    "ts_argmax",
    "ts_argmin",
    "product",
    "decay_linear",
    # Cross-sectional operators
    "rank",
    "scale",
    # Statistical operators
    "correlation",
    "covariance",
    # Arithmetic operators
    "log",
    "sign",
    "abs_",
    # Client
    "FactorClient",
    "FactorClientError",
    "get_factor_client",
    # Tools
    "search_factors",
    "get_factor_code",
    "list_factor_categories",
]
