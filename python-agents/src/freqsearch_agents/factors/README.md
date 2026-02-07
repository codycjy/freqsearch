# Factor Client and Tools

HTTP client and LangChain tools for accessing the FreqSearch quantitative factor library.

## Overview

This module provides Python agents with on-demand access to a structured factor library, avoiding context pollution and enabling efficient factor discovery and integration.

## Components

### 1. FactorClient (`client.py`)

Async HTTP client for Factor API interactions.

**Features:**
- Async/await support with context manager
- Multi-dimensional factor search
- Error handling with custom exceptions
- Configuration via settings

**Example:**
```python
from freqsearch_agents.factors import FactorClient

async with FactorClient() as client:
    # Search for momentum factors
    factors = await client.search(
        category="momentum",
        holding_period="short",
        limit=10
    )

    # Get specific factor
    factor = await client.get_by_name("alpha_001")

    # Get category statistics
    stats = await client.get_category_stats()
```

### 2. LangChain Tools (`tools.py`)

Three tools for agent integration:

#### `search_factors`

Search factor library with filters.

**Parameters:**
- `category`: Factor category (momentum/mean_reversion/volatility/volume/price_pattern)
- `signal_type`: Signal type (entry/exit/filter/sizing/alpha)
- `holding_period`: Holding period (intraday/short/medium/long)
- `data_requirement`: Data needs (price_only/volume/vwap/industry/fundamental)
- `market_regime`: Market environment (trending/ranging/volatile/any)
- `keyword`: Text search in descriptions
- `limit`: Max results (default: 5)

**Returns:** JSON list of factor summaries

**Example:**
```python
from freqsearch_agents.factors import search_factors

result = search_factors.invoke({
    "category": "momentum",
    "holding_period": "short",
    "limit": 5
})
```

#### `get_factor_code`

Get complete factor implementation.

**Parameters:**
- `factor_name`: Factor name (e.g., "alpha_001")

**Returns:** Markdown document with:
- Factor description and classification
- Mathematical expression
- Complete Python code
- Usage examples

**Example:**
```python
from freqsearch_agents.factors import get_factor_code

code = get_factor_code.invoke({"factor_name": "alpha_001"})
```

#### `list_factor_categories`

Get factor library statistics.

**Returns:** Category counts and percentages

**Example:**
```python
from freqsearch_agents.factors import list_factor_categories

stats = list_factor_categories.invoke({})
```

## Configuration

Add to `.env`:

```bash
FACTOR_API_URL=http://localhost:8083/api/v1  # Factor API base URL
```

Or use defaults from `config.py`:
```python
class FactorSettings(BaseSettings):
    api_url: str = Field("http://localhost:8083/api/v1", alias="FACTOR_API_URL")
    timeout_seconds: int = 30
```

## API Endpoints

The client expects these Go backend endpoints:

```
GET  /api/v1/factors              # Search with filters
GET  /api/v1/factors/:id          # Get by ID
GET  /api/v1/factors/categories   # Category statistics
POST /api/v1/factors              # Create factor
```

## Integration with Agents

### Engineer Agent

Add tools to Engineer agent:

```python
from freqsearch_agents.factors import (
    search_factors,
    get_factor_code,
    list_factor_categories,
)

ENGINEER_TOOLS = [
    # ... existing tools
    search_factors,
    get_factor_code,
    list_factor_categories,
]
```

Update prompt:

```python
FACTOR_GUIDANCE = """
## Factor Library

You have access to a quantitative factor library with 101+ alpha factors.

**Workflow:**
1. Use `list_factor_categories()` to explore available categories
2. Use `search_factors(category=..., ...)` to find relevant factors
3. Use `get_factor_code(factor_name)` to get implementation
4. Integrate factor code into strategy

**Categories:**
- momentum: Price momentum and trends
- mean_reversion: Price reversion patterns
- volatility: Market volatility metrics
- volume: Volume-price relationships
- price_pattern: Technical patterns
"""
```

## Error Handling

All tools gracefully handle errors and return user-friendly messages:

```python
# Backend not available
result = search_factors.invoke({"category": "momentum"})
# Returns: "搜索因子时出错: HTTP 404: 404 page not found"

# Factor not found
code = get_factor_code.invoke({"factor_name": "invalid"})
# Returns: "因子 'invalid' 不存在。请使用 search_factors 工具查找可用因子。"
```

## Testing

Run the test script:

```bash
cd python-agents
conda run -n freq python test_factor_tools.py
```

**Note:** Requires Go backend with Factor API endpoints running.

## Architecture

```
┌─────────────────────────────────────────┐
│         LangChain Tools                  │
│  (search_factors, get_factor_code, ...)  │
└──────────────┬───────────────────────────┘
               │ Sync wrapper (asyncio.run)
               ▼
┌─────────────────────────────────────────┐
│         FactorClient                     │
│  (async HTTP client with httpx)         │
└──────────────┬───────────────────────────┘
               │ HTTP REST API
               ▼
┌─────────────────────────────────────────┐
│       Go Backend Factor API              │
│     GET /api/v1/factors                  │
└─────────────────────────────────────────┘
```

## Design Decisions

1. **Tool-based Access**: Factors queried on-demand via tools, not injected into prompts, minimizing context consumption

2. **Async-first Client**: Uses `httpx.AsyncClient` for efficient async operations, with sync wrappers for LangChain tool compatibility

3. **Graceful Degradation**: Tools return error messages instead of raising exceptions, allowing agents to continue execution

4. **Configuration-driven**: Uses Pydantic settings with environment variable support

5. **Token Optimization**: Tools return concise summaries for search, full details only when requested via `get_factor_code`

## Dependencies

```python
httpx>=0.27.0          # Async HTTP client
structlog>=24.0.0      # Structured logging
langchain-core>=0.1.0  # Tool decorator
pydantic>=2.0.0        # Settings validation
```

## Future Enhancements

- [ ] Caching layer for frequently accessed factors
- [ ] Batch operations for multiple factors
- [ ] Factor performance metrics integration
- [ ] Local factor library fallback
- [ ] Vector similarity search for factor discovery
