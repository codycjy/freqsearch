"""LangChain tools for Factor library access."""

import asyncio
import json

import structlog
from langchain_core.tools import tool

from .client import FactorClient

logger = structlog.get_logger(__name__)


def _run_async(coro):
    """Run async coroutine in sync context.

    Handles both new and existing event loops.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Running in async context - create new task
            return loop.run_until_complete(coro)
        else:
            # No running loop - use run
            return loop.run_until_complete(coro)
    except RuntimeError:
        # No event loop - create new one
        return asyncio.run(coro)


async def _async_search_factors(
    category: str | None = None,
    signal_type: str | None = None,
    holding_period: str | None = None,
    data_requirement: str | None = None,
    market_regime: str | None = None,
    keyword: str | None = None,
    limit: int = 5,
) -> str:
    """Internal async implementation of search_factors."""
    async with FactorClient() as client:
        factors = await client.search(
            category=category,
            signal_type=signal_type,
            holding_period=holding_period,
            data_requirement=data_requirement,
            market_regime=market_regime,
            keyword=keyword,
            limit=limit,
        )

        if not factors:
            return "未找到符合条件的因子。请尝试调整搜索条件。"

        # Format concise results for LLM
        result = []
        for f in factors:
            # Truncate long expressions
            expr = f.get("expression", "")
            if len(expr) > 80:
                expr = expr[:77] + "..."

            result.append({
                "name": f.get("name"),
                "category": f.get("category"),
                "holding_period": f.get("holding_period"),
                "description": f.get("description", "")[:150],  # Truncate description
                "expression": expr,
            })

        return json.dumps(result, ensure_ascii=False, indent=2)


async def _async_get_factor_code(factor_name: str) -> str:
    """Internal async implementation of get_factor_code."""
    async with FactorClient() as client:
        factor = await client.get_by_name(factor_name)

        if not factor:
            return f"因子 '{factor_name}' 不存在。请使用 search_factors 工具查找可用因子。"

        # Format complete factor information
        output = f"""## {factor.get('name', '').upper()}

**描述**: {factor.get('description', 'N/A')}
**类别**: {factor.get('category', 'N/A')} | **持仓期**: {factor.get('holding_period', 'N/A')}
**信号类型**: {factor.get('signal_type', 'N/A')} | **数据需求**: {factor.get('data_requirement', 'N/A')}
**公式**: {factor.get('expression', 'N/A')}

**代码实现**:
```python
{factor.get('code_template', '# 代码未提供')}
```

**使用示例**:
```python
# 在 Freqtrade 策略中使用该因子
dataframe['{factor.get('name', 'factor')}'] = {factor.get('name', 'factor')}(dataframe)

# 示例: 将因子用作入场信号
dataframe.loc[
    (dataframe['{factor.get('name', 'factor')}'] > threshold),
    'enter_long'
] = 1
```
"""
        return output


async def _async_list_factor_categories() -> str:
    """Internal async implementation of list_factor_categories."""
    async with FactorClient() as client:
        stats = await client.get_category_stats()

        if not stats:
            return "因子库为空或无法获取分类统计。"

        # Format category statistics
        output = "# 因子库分类统计\n\n"
        total = sum(stats.values())
        output += f"**总计**: {total} 个因子\n\n"

        # Sort by count (descending)
        sorted_stats = sorted(stats.items(), key=lambda x: x[1], reverse=True)

        for category, count in sorted_stats:
            percentage = (count / total * 100) if total > 0 else 0
            output += f"- **{category}**: {count} 个 ({percentage:.1f}%)\n"

        return output


@tool
def search_factors(
    category: str | None = None,
    signal_type: str | None = None,
    holding_period: str | None = None,
    data_requirement: str | None = None,
    market_regime: str | None = None,
    keyword: str | None = None,
    limit: int = 5,
) -> str:
    """搜索量化因子库。

    支持多维度过滤条件，找到符合策略需求的量化因子。返回因子的基本信息摘要。

    Args:
        category: 因子类别 (momentum/mean_reversion/volatility/volume/price_pattern)
            - momentum: 动量类因子，捕捉价格趋势
            - mean_reversion: 均值回归类，捕捉价格回归
            - volatility: 波动率类，衡量市场波动
            - volume: 成交量类，分析交易活跃度
            - price_pattern: 价格形态类，识别技术形态
        signal_type: 信号类型 (entry/exit/filter/sizing/alpha)
            - entry: 入场信号
            - exit: 出场信号
            - filter: 过滤条件
            - sizing: 仓位管理
            - alpha: 收益预测
        holding_period: 持仓周期 (intraday/short/medium/long)
            - intraday: 日内
            - short: 短期 (1-3天)
            - medium: 中期 (3-10天)
            - long: 长期 (10天以上)
        data_requirement: 数据需求 (price_only/volume/vwap/industry/fundamental)
            - price_only: 仅需价格数据
            - volume: 需要成交量
            - vwap: 需要VWAP数据
            - industry: 需要行业数据
            - fundamental: 需要基本面数据
        market_regime: 适用市场环境 (trending/ranging/volatile/any)
            - trending: 趋势市场
            - ranging: 震荡市场
            - volatile: 高波动市场
            - any: 任意市场
        keyword: 关键词搜索 (在因子描述中搜索)
        limit: 返回结果数量 (默认: 5)

    Returns:
        JSON格式的因子列表，包含名称、类别、周期、描述和公式摘要

    Examples:
        # 搜索短期动量因子
        search_factors(category="momentum", holding_period="short")

        # 搜索仅需价格的入场信号
        search_factors(signal_type="entry", data_requirement="price_only")

        # 关键词搜索
        search_factors(keyword="价量背离")
    """
    try:
        return _run_async(
            _async_search_factors(
                category=category,
                signal_type=signal_type,
                holding_period=holding_period,
                data_requirement=data_requirement,
                market_regime=market_regime,
                keyword=keyword,
                limit=limit,
            )
        )
    except Exception as e:
        logger.error("Error searching factors", error=str(e))
        return f"搜索因子时出错: {str(e)}"


@tool
def get_factor_code(factor_name: str) -> str:
    """获取因子的完整代码实现。

    返回指定因子的详细信息，包括完整的Python实现代码和使用示例。

    Args:
        factor_name: 因子名称 (如 "alpha_001", "alpha_002" 等)

    Returns:
        因子的完整信息，包括:
        - 描述和分类标签
        - 数学公式表达式
        - 可执行的Python代码
        - 在Freqtrade策略中的使用示例

    Examples:
        # 获取alpha_001的完整代码
        get_factor_code("alpha_001")
    """
    try:
        return _run_async(_async_get_factor_code(factor_name))
    except Exception as e:
        logger.error("Error getting factor code", factor_name=factor_name, error=str(e))
        return f"获取因子代码时出错: {str(e)}"


@tool
def list_factor_categories() -> str:
    """列出因子库的分类统计。

    返回因子库中各类别的因子数量统计，帮助了解因子库的整体结构。

    Returns:
        因子库分类统计，包括每个类别的因子数量和占比

    Examples:
        # 查看因子库结构
        list_factor_categories()
    """
    try:
        return _run_async(_async_list_factor_categories())
    except Exception as e:
        logger.error("Error listing factor categories", error=str(e))
        return f"获取因子分类统计时出错: {str(e)}"


# Export all tools
__all__ = [
    "search_factors",
    "get_factor_code",
    "list_factor_categories",
]
