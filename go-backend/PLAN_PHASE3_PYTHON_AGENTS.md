# Phase 3: Python Agents Implementation Plan

## 1. Architecture Overview

### 1.1 Agent Responsibilities (Refined)

| Agent | 职责 | 运行模式 | 触发条件 |
|-------|------|---------|---------|
| **Scout** | 发现策略、清洗、去重 | Cron + Manual | 定时任务或手动触发 |
| **Engineer** | 代码生成、修复、超参空间定义 | MQ Consumer | 收到 RawStrategy 或 DiagnosisReport |
| **Analyst** | 回测结果分析、进化决策 | MQ Consumer | 收到 BacktestCompleted 事件 |

> **Note**: Commander Agent 已移除，其职责由 Go Backend 的 Scheduler + Docker Manager 承担。

### 1.2 Communication Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              EVENT FLOW                                   │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  [Scout Agent]                                                           │
│       │ (Cron/Manual)                                                    │
│       ▼                                                                  │
│  ┌─────────────────┐                                                     │
│  │ RawStrategy     │──────► RabbitMQ: strategy.discovered               │
│  └─────────────────┘                    │                                │
│                                         ▼                                │
│                              [Go Backend: Create Strategy Record]        │
│                                         │                                │
│                                         ▼                                │
│                              RabbitMQ: strategy.needs_processing         │
│                                         │                                │
│                                         ▼                                │
│  [Engineer Agent]◄──────────────────────┘                                │
│       │                                                                  │
│       ▼                                                                  │
│  ┌─────────────────┐                                                     │
│  │ExecutableStrategy│─────► RabbitMQ: strategy.ready_for_backtest       │
│  │+ HyperoptConfig │                    │                                │
│  └─────────────────┘                    ▼                                │
│                              [Go Backend: Schedule Backtest Job]         │
│                                         │                                │
│                                         ▼                                │
│                              [Docker: Run Freqtrade Backtest]            │
│                                         │                                │
│                                         ▼                                │
│                              [Go Backend: Parse & Store Results]         │
│                                         │                                │
│                                         ▼                                │
│                              RabbitMQ: backtest.completed                │
│                                         │                                │
│                                         ▼                                │
│  [Analyst Agent]◄───────────────────────┘                                │
│       │                                                                  │
│       ▼                                                                  │
│  ┌─────────────────┐                                                     │
│  │DiagnosisReport  │                                                     │
│  └────────┬────────┘                                                     │
│           │                                                              │
│           ├──► status=READY_FOR_LIVE ──► RabbitMQ: strategy.approved    │
│           │                                                              │
│           └──► status=NEEDS_MODIFICATION ──► RabbitMQ: strategy.evolve  │
│                                                       │                  │
│                                                       ▼                  │
│                                              [Engineer Agent] (Loop)     │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### 1.3 Technology Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Agent Framework | **LangGraph** | 状态机支持、工具调用、循环推理 |
| LLM | **OpenAI GPT-4** | 代码生成能力强 |
| Embeddings | **OpenAI text-embedding-3-small** | 与 LLM 统一供应商 |
| Vector Store | **PGVector** | 复用现有 PostgreSQL |
| Message Queue | **RabbitMQ** | 复用现有基础设施 |
| Sync API | **gRPC** | 与 Go Backend 一致 |

---

## 2. Project Structure

```
python-agents/
├── pyproject.toml                 # Poetry/UV 依赖管理
├── .env.example                   # 环境变量模板
├── Dockerfile
├── docker-compose.override.yml   # 与主 compose 合并
│
├── src/
│   └── freqsearch_agents/
│       ├── __init__.py
│       ├── main.py               # Entry point (CLI + daemon)
│       ├── config.py             # Pydantic Settings
│       │
│       ├── core/                 # 核心基础设施
│       │   ├── __init__.py
│       │   ├── llm.py            # OpenAI client wrapper
│       │   ├── embeddings.py     # Embedding model
│       │   ├── vectorstore.py    # PGVector client
│       │   ├── messaging.py      # RabbitMQ consumer/producer
│       │   ├── grpc_client.py    # Go Backend gRPC client
│       │   └── state.py          # LangGraph state definitions
│       │
│       ├── agents/               # Agent 实现
│       │   ├── __init__.py
│       │   ├── base.py           # Base agent class
│       │   ├── scout/
│       │   │   ├── __init__.py
│       │   │   ├── agent.py      # Scout LangGraph definition
│       │   │   ├── nodes.py      # Graph nodes
│       │   │   └── prompts.py    # Prompt templates
│       │   ├── engineer/
│       │   │   ├── __init__.py
│       │   │   ├── agent.py
│       │   │   ├── nodes.py
│       │   │   └── prompts.py
│       │   └── analyst/
│       │       ├── __init__.py
│       │       ├── agent.py
│       │       ├── nodes.py
│       │       └── prompts.py
│       │
│       ├── tools/                # LangChain Tools
│       │   ├── __init__.py
│       │   ├── base.py           # Tool base class
│       │   ├── sources/          # 策略数据源
│       │   │   ├── __init__.py
│       │   │   ├── base.py       # StrategySource ABC
│       │   │   └── stratninja.py # strat.ninja 实现
│       │   ├── code/             # 代码处理工具
│       │   │   ├── __init__.py
│       │   │   ├── parser.py     # AST parsing
│       │   │   ├── validator.py  # Syntax validation
│       │   │   └── simhash.py    # Deduplication
│       │   └── analysis/         # 分析工具
│       │       ├── __init__.py
│       │       ├── metrics.py    # 指标计算
│       │       └── attribution.py # 归因分析
│       │
│       ├── schemas/              # Pydantic models (共享数据结构)
│       │   ├── __init__.py
│       │   ├── strategy.py       # RawStrategy, ExecutableStrategy
│       │   ├── diagnosis.py      # DiagnosisReport
│       │   └── events.py         # MQ message schemas
│       │
│       └── knowledge/            # RAG 知识库
│           ├── __init__.py
│           ├── indexer.py        # 文档索引器
│           └── documents/        # 待索引文档
│               ├── freqtrade_docs.md
│               └── talib_reference.md
│
├── tests/
│   ├── conftest.py
│   ├── test_tools/
│   ├── test_agents/
│   └── fixtures/
│
└── scripts/
    ├── index_knowledge.py        # 初始化向量库
    └── run_scout_once.py         # 手动触发 Scout
```

---

## 3. Implementation Phases

### Phase 3.1: Core Infrastructure (Days 1-2)

#### 3.1.1 Tasks

- [ ] Initialize Python project with Poetry/UV
- [ ] Setup Pydantic Settings for configuration
- [ ] Implement OpenAI LLM client wrapper
- [ ] Implement PGVector client (reuse existing PG connection)
- [ ] Implement RabbitMQ consumer/producer
- [ ] Generate gRPC client stubs from proto files
- [ ] Define LangGraph state schemas

#### 3.1.2 Key Files

```python
# src/freqsearch_agents/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # OpenAI
    openai_api_key: str
    openai_model: str = "gpt-4-turbo-preview"

    # Database
    database_url: str

    # RabbitMQ
    rabbitmq_url: str

    # gRPC
    go_backend_grpc_addr: str = "localhost:50051"

    class Config:
        env_file = ".env"
```

```python
# src/freqsearch_agents/core/state.py
from typing import TypedDict, Annotated, List
from langgraph.graph.message import add_messages

class ScoutState(TypedDict):
    """Scout Agent 的状态定义"""
    messages: Annotated[list, add_messages]
    raw_strategies: List[dict]
    deduplicated_count: int
    current_source: str

class EngineerState(TypedDict):
    """Engineer Agent 的状态定义"""
    messages: Annotated[list, add_messages]
    input_strategy: dict           # RawStrategy or DiagnosisReport
    mode: str                      # "new" | "fix" | "evolve"
    generated_code: str
    hyperopt_config: dict
    validation_errors: List[str]

class AnalystState(TypedDict):
    """Analyst Agent 的状态定义"""
    messages: Annotated[list, add_messages]
    backtest_result: dict
    metrics: dict
    diagnosis: dict
    decision: str                  # "approve" | "modify" | "archive"
```

---

### Phase 3.2: Tools Implementation (Days 3-4)

#### 3.2.1 StrategySource Interface

```python
# src/freqsearch_agents/tools/sources/base.py
from abc import ABC, abstractmethod
from typing import List
from langchain_core.tools import BaseTool
from pydantic import BaseModel

class RawStrategy(BaseModel):
    """从数据源获取的原始策略"""
    source_url: str
    source_name: str  # e.g., "strat.ninja", "github"
    name: str
    code: str
    description: str | None = None
    detected_indicators: List[str] = []
    code_hash: str  # For deduplication

class StrategySource(ABC):
    """策略数据源抽象基类"""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """数据源名称"""
        ...

    @abstractmethod
    async def fetch_strategies(
        self,
        limit: int = 50,
        filters: dict | None = None
    ) -> List[RawStrategy]:
        """获取策略列表"""
        ...

    @abstractmethod
    async def fetch_strategy_code(self, url: str) -> str:
        """获取单个策略的完整代码"""
        ...

    def as_langchain_tool(self) -> BaseTool:
        """转换为 LangChain Tool"""
        from langchain_core.tools import StructuredTool

        return StructuredTool.from_function(
            func=self._tool_func,
            name=f"fetch_strategies_from_{self.source_name}",
            description=f"Fetch trading strategies from {self.source_name}",
        )

    async def _tool_func(self, limit: int = 20) -> str:
        """Tool 调用入口"""
        strategies = await self.fetch_strategies(limit=limit)
        return f"Found {len(strategies)} strategies: {[s.name for s in strategies]}"
```

#### 3.2.2 StratNinja Implementation

```python
# src/freqsearch_agents/tools/sources/stratninja.py
import httpx
from bs4 import BeautifulSoup
from .base import StrategySource, RawStrategy

class StratNinjaSource(StrategySource):
    """strat.ninja 数据源实现"""

    BASE_URL = "https://strat.ninja"

    @property
    def source_name(self) -> str:
        return "stratninja"

    async def fetch_strategies(
        self,
        limit: int = 50,
        filters: dict | None = None
    ) -> List[RawStrategy]:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.BASE_URL}/strats.php")
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        strategies = []

        # Parse strategy list (需要根据实际页面结构调整)
        for row in soup.select("table tr")[1:limit+1]:
            # Extract strategy info
            name = row.select_one(".strategy-name").text
            url = row.select_one("a")["href"]

            strategies.append(RawStrategy(
                source_url=f"{self.BASE_URL}{url}",
                source_name=self.source_name,
                name=name,
                code="",  # 延迟加载
                code_hash="",
            ))

        return strategies

    async def fetch_strategy_code(self, url: str) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        code_block = soup.select_one("pre.strategy-code")

        if code_block:
            return code_block.text
        return ""
```

#### 3.2.3 Code Tools

```python
# src/freqsearch_agents/tools/code/parser.py
import ast
from typing import List, Dict

class FreqtradeCodeParser:
    """解析 Freqtrade 策略代码"""

    REQUIRED_METHODS = [
        "populate_indicators",
        "populate_entry_trend",
        "populate_exit_trend",
    ]

    def parse(self, code: str) -> Dict:
        """解析策略代码，提取结构信息"""
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return {"valid": False, "error": str(e)}

        result = {
            "valid": True,
            "class_name": None,
            "methods": [],
            "indicators": [],
            "parameters": [],
            "hardcoded_values": [],
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # 检查是否继承 IStrategy
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == "IStrategy":
                        result["class_name"] = node.name
                        result["methods"] = [
                            m.name for m in node.body
                            if isinstance(m, ast.FunctionDef)
                        ]

            # 检测硬编码数值 (用于生成 Hyperopt 空间)
            if isinstance(node, ast.Num):
                result["hardcoded_values"].append({
                    "value": node.n,
                    "line": node.lineno,
                })

        # 检查必需方法
        result["missing_methods"] = [
            m for m in self.REQUIRED_METHODS
            if m not in result["methods"]
        ]

        return result
```

```python
# src/freqsearch_agents/tools/code/simhash.py
from simhash import Simhash

def compute_code_hash(code: str) -> str:
    """计算代码的 SimHash，用于去重"""
    # 预处理：移除空白、注释
    lines = []
    for line in code.split("\n"):
        line = line.strip()
        if line and not line.startswith("#"):
            lines.append(line)

    normalized = " ".join(lines)
    return str(Simhash(normalized).value)

def is_duplicate(hash1: str, hash2: str, threshold: int = 3) -> bool:
    """判断两个代码是否相似（Hamming distance < threshold）"""
    h1, h2 = int(hash1), int(hash2)
    return bin(h1 ^ h2).count("1") < threshold
```

---

### Phase 3.3: Scout Agent (Days 5-6)

#### 3.3.1 LangGraph Definition

```python
# src/freqsearch_agents/agents/scout/agent.py
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from ...core.state import ScoutState
from ...tools.sources.stratninja import StratNinjaSource
from .nodes import (
    fetch_strategies_node,
    validate_code_node,
    deduplicate_node,
    submit_strategies_node,
)

def create_scout_agent():
    """创建 Scout Agent 的 LangGraph"""

    # 初始化工具
    sources = [StratNinjaSource()]
    tools = [s.as_langchain_tool() for s in sources]

    # 构建图
    workflow = StateGraph(ScoutState)

    # 添加节点
    workflow.add_node("fetch", fetch_strategies_node)
    workflow.add_node("validate", validate_code_node)
    workflow.add_node("deduplicate", deduplicate_node)
    workflow.add_node("submit", submit_strategies_node)

    # 定义边
    workflow.set_entry_point("fetch")
    workflow.add_edge("fetch", "validate")
    workflow.add_edge("validate", "deduplicate")
    workflow.add_edge("deduplicate", "submit")
    workflow.add_edge("submit", END)

    return workflow.compile()
```

#### 3.3.2 Node Implementations

```python
# src/freqsearch_agents/agents/scout/nodes.py
from ...core.state import ScoutState
from ...tools.sources.stratninja import StratNinjaSource
from ...tools.code.parser import FreqtradeCodeParser
from ...tools.code.simhash import compute_code_hash, is_duplicate
from ...core.messaging import publish_event

async def fetch_strategies_node(state: ScoutState) -> ScoutState:
    """从数据源获取策略"""
    source = StratNinjaSource()
    strategies = await source.fetch_strategies(limit=50)

    # 获取每个策略的完整代码
    for strategy in strategies:
        strategy.code = await source.fetch_strategy_code(strategy.source_url)
        strategy.code_hash = compute_code_hash(strategy.code)

    return {
        **state,
        "raw_strategies": [s.model_dump() for s in strategies],
        "current_source": source.source_name,
    }

async def validate_code_node(state: ScoutState) -> ScoutState:
    """验证代码完整性"""
    parser = FreqtradeCodeParser()
    valid_strategies = []

    for strategy in state["raw_strategies"]:
        result = parser.parse(strategy["code"])

        if result["valid"] and not result["missing_methods"]:
            strategy["parse_result"] = result
            valid_strategies.append(strategy)
        # TODO: 不完整的代码可以尝试 LLM 补全

    return {**state, "raw_strategies": valid_strategies}

async def deduplicate_node(state: ScoutState) -> ScoutState:
    """去重"""
    # TODO: 从数据库获取已有策略的 hash
    existing_hashes = []  # await get_existing_hashes()

    unique_strategies = []
    for strategy in state["raw_strategies"]:
        is_dup = any(
            is_duplicate(strategy["code_hash"], h)
            for h in existing_hashes
        )
        if not is_dup:
            unique_strategies.append(strategy)

    return {
        **state,
        "raw_strategies": unique_strategies,
        "deduplicated_count": len(state["raw_strategies"]) - len(unique_strategies),
    }

async def submit_strategies_node(state: ScoutState) -> ScoutState:
    """提交到消息队列"""
    for strategy in state["raw_strategies"]:
        await publish_event(
            exchange="freqsearch",
            routing_key="strategy.discovered",
            body=strategy,
        )

    return state
```

---

### Phase 3.4: Engineer Agent (Days 7-9)

#### 3.4.1 核心功能

1. **新策略处理** (mode="new")
   - 修复语法错误
   - 适配 Freqtrade API
   - 生成 Hyperopt 空间

2. **进化处理** (mode="evolve")
   - 根据 DiagnosisReport 修改逻辑
   - RAG 查询指标用法
   - 注入新条件

#### 3.4.2 LangGraph Definition

```python
# src/freqsearch_agents/agents/engineer/agent.py
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from ...core.state import EngineerState
from ...core.llm import get_llm
from .nodes import (
    analyze_input_node,
    rag_lookup_node,
    generate_code_node,
    validate_code_node,
    generate_hyperopt_node,
    submit_node,
)

def create_engineer_agent():
    """创建 Engineer Agent 的 LangGraph"""

    workflow = StateGraph(EngineerState)

    # 节点
    workflow.add_node("analyze", analyze_input_node)
    workflow.add_node("rag_lookup", rag_lookup_node)
    workflow.add_node("generate", generate_code_node)
    workflow.add_node("validate", validate_code_node)
    workflow.add_node("hyperopt", generate_hyperopt_node)
    workflow.add_node("submit", submit_node)

    # 边
    workflow.set_entry_point("analyze")
    workflow.add_edge("analyze", "rag_lookup")
    workflow.add_edge("rag_lookup", "generate")

    # 条件边：验证失败则重新生成
    workflow.add_conditional_edges(
        "generate",
        lambda s: "retry" if s["validation_errors"] else "continue",
        {
            "retry": "generate",  # 最多重试 3 次
            "continue": "validate",
        }
    )

    workflow.add_edge("validate", "hyperopt")
    workflow.add_edge("hyperopt", "submit")
    workflow.add_edge("submit", END)

    return workflow.compile(checkpointer=MemorySaver())
```

#### 3.4.3 Key Prompts

```python
# src/freqsearch_agents/agents/engineer/prompts.py

SYSTEM_PROMPT = """You are an expert Freqtrade strategy engineer. Your job is to:
1. Fix syntax errors in trading strategy code
2. Ensure compatibility with Freqtrade's latest API
3. Generate hyperparameter search spaces for optimization

Rules:
- Always use dataframe operations (no loops over rows)
- Use ta-lib indicators via the `ta` module
- Parameters must be defined as class attributes using IntParameter/DecimalParameter
- Entry/exit conditions must use boolean Series with bitwise operators (&, |)
"""

CODE_GENERATION_PROMPT = """
Given the following input:

## Original Strategy
```python
{original_code}
```

## Modification Request
{modification_request}

## Relevant Documentation
{rag_context}

Generate a corrected/improved strategy that:
1. Fixes any syntax errors
2. Implements the requested modifications
3. Uses proper Freqtrade conventions

Output ONLY the Python code, no explanations.
"""

HYPEROPT_GENERATION_PROMPT = """
Analyze this strategy code and generate a hyperopt configuration:

```python
{strategy_code}
```

For each hardcoded numeric value that could be optimized:
1. Identify the parameter name
2. Suggest a reasonable search range
3. Choose the appropriate parameter type (IntParameter/DecimalParameter)

Output as JSON:
{
  "parameters": [
    {"name": "rsi_period", "type": "int", "low": 7, "high": 21, "default": 14},
    {"name": "rsi_buy_threshold", "type": "float", "low": 20, "high": 40, "default": 30}
  ]
}
"""
```

---

### Phase 3.5: Analyst Agent (Days 10-12)

#### 3.5.1 核心功能

1. **多维指标计算**
   - Sharpe/Sortino/Calmar Ratio
   - Win Rate, Expectancy
   - Max Drawdown Duration

2. **微观归因分析**
   - 亏损单市场状态分析
   - 过拟合检测

3. **进化决策**
   - APPROVE: 策略合格
   - MODIFY: 需要修改（生成 DiagnosisReport）
   - ARCHIVE: 策略废弃

#### 3.5.2 DiagnosisReport Schema

```python
# src/freqsearch_agents/schemas/diagnosis.py
from pydantic import BaseModel
from typing import List, Literal
from enum import Enum

class DiagnosisStatus(str, Enum):
    READY_FOR_LIVE = "READY_FOR_LIVE"
    NEEDS_MODIFICATION = "NEEDS_MODIFICATION"
    ARCHIVE = "ARCHIVE"

class SuggestionType(str, Enum):
    ADD_FILTER = "ADD_FILTER"           # 添加过滤条件
    MODIFY_PARAMETER = "MODIFY_PARAMETER"  # 修改参数范围
    ADD_STOPLOSS = "ADD_STOPLOSS"       # 添加/修改止损
    CHANGE_TIMEFRAME = "CHANGE_TIMEFRAME"  # 更换时间周期
    ADD_INDICATOR = "ADD_INDICATOR"     # 添加指标

class DiagnosisReport(BaseModel):
    """Analyst Agent 的诊断报告"""

    job_id: str
    strategy_id: str

    # 决策
    status: DiagnosisStatus
    confidence: float  # 0-1

    # 诊断详情
    issues: List[str]
    root_causes: List[str]

    # 修改建议 (仅当 status=NEEDS_MODIFICATION)
    suggestion_type: SuggestionType | None = None
    logic_description: str | None = None
    target_metrics: List[str] = []

    # 统计摘要
    metrics_summary: dict
```

#### 3.5.3 Analysis Prompts

```python
# src/freqsearch_agents/agents/analyst/prompts.py

ANALYSIS_PROMPT = """
You are a quantitative trading analyst. Analyze this backtest result:

## Strategy: {strategy_name}
## Backtest Period: {start_date} to {end_date}

## Performance Metrics
- Total Trades: {total_trades}
- Win Rate: {win_rate}%
- Profit: {profit_pct}%
- Max Drawdown: {max_drawdown}%
- Sharpe Ratio: {sharpe_ratio}
- Profit Factor: {profit_factor}

## Trade Analysis
Winning trades average: {avg_win}%
Losing trades average: {avg_loss}%

## Losing Trades Context
{losing_trades_context}

Based on this analysis:
1. Identify the main issues with this strategy
2. Determine the root causes
3. Recommend specific modifications

Output as JSON matching the DiagnosisReport schema.
"""
```

---

### Phase 3.6: Integration & Testing (Days 13-15)

#### 3.6.1 Go Backend Updates

需要在 Go Backend 添加的支持：

```go
// internal/events/types.go - 新增事件类型
const (
    EventStrategyDiscovered    = "strategy.discovered"
    EventStrategyNeedsProcess  = "strategy.needs_processing"
    EventStrategyReadyBacktest = "strategy.ready_for_backtest"
    EventBacktestCompleted     = "backtest.completed"
    EventStrategyApproved      = "strategy.approved"
    EventStrategyEvolve        = "strategy.evolve"
)

// internal/api/grpc/server.go - 新增方法
func (s *Server) CreateStrategyFromAgent(ctx context.Context, req *pb.CreateStrategyFromAgentRequest) (*pb.CreateStrategyFromAgentResponse, error)
func (s *Server) GetStrategyCodeHash(ctx context.Context, req *pb.GetStrategyCodeHashRequest) (*pb.GetStrategyCodeHashResponse, error)
```

#### 3.6.2 Docker Compose Integration

```yaml
# docker-compose.override.yml
services:
  python-agents:
    build: ./python-agents
    depends_on:
      - go-backend
      - rabbitmq
      - postgres
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - DATABASE_URL=postgresql://user:pass@postgres:5432/freqsearch
      - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672/
      - GO_BACKEND_GRPC_ADDR=go-backend:50051
    volumes:
      - ./python-agents/src:/app/src
```

#### 3.6.3 Test Strategy

```
tests/
├── unit/
│   ├── test_code_parser.py
│   ├── test_simhash.py
│   └── test_metrics.py
├── integration/
│   ├── test_scout_agent.py
│   ├── test_engineer_agent.py
│   └── test_analyst_agent.py
└── e2e/
    └── test_full_evolution_loop.py
```

---

## 4. Key Design Decisions

### 4.1 为什么移除 Commander Agent？

| 原 Commander 职责 | 现由谁承担 | 原因 |
|------------------|-----------|------|
| Docker 容器管理 | Go `docker/manager.go` | 已实现，避免重复 |
| 任务调度 | Go `scheduler/scheduler.go` | 已实现，Go 更适合 |
| 配置生成 | Go + Engineer Agent | 静态配置在 Go，动态参数在 Engineer |
| 进度监控 | Go `events/` | 事件驱动，复用 RabbitMQ |

### 4.2 Agent 通信模式

```
异步任务 (MQ):
- strategy.discovered → Engineer 处理新策略
- backtest.completed → Analyst 分析结果
- strategy.evolve → Engineer 进化策略

同步查询 (gRPC):
- Engineer 查询已有策略 hash (去重)
- Analyst 查询历史回测数据
- Agent 提交生成的策略代码
```

### 4.3 RAG 知识库内容

优先索引:
1. Freqtrade 官方文档 (策略开发部分)
2. TA-Lib 指标参考
3. 常见策略模式示例
4. Freqtrade API 变更日志

---

## 5. Risk & Mitigation

| 风险 | 影响 | 缓解措施 |
|-----|------|---------|
| LLM 生成代码有 bug | 回测失败 | 多轮验证 + AST 检查 |
| strat.ninja 反爬 | Scout 失效 | 多数据源、请求限速 |
| OpenAI API 成本 | 费用超支 | 缓存、批量处理、小模型筛选 |
| Agent 死循环 | 资源耗尽 | 最大迭代次数限制 |

---

## 6. Success Metrics

Phase 3 完成标准:

- [ ] Scout 能从 strat.ninja 获取并去重策略
- [ ] Engineer 能修复语法错误并生成 hyperopt 空间
- [ ] Analyst 能分析回测结果并生成 DiagnosisReport
- [ ] 完整循环: Scout → Engineer → Backtest → Analyst → Engineer (evolve)
- [ ] 单元测试覆盖率 > 70%
- [ ] 端到端测试通过

---

## 7. Timeline Summary

| Phase | 任务 | 预计天数 |
|-------|-----|---------|
| 3.1 | Core Infrastructure | 2 |
| 3.2 | Tools Implementation | 2 |
| 3.3 | Scout Agent | 2 |
| 3.4 | Engineer Agent | 3 |
| 3.5 | Analyst Agent | 3 |
| 3.6 | Integration & Testing | 3 |
| **Total** | | **15 days** |
