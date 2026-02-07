"""LangGraph definition for single-iteration optimization.

支持两种模式:
1. Baseline 模式 (iteration 0): 直接运行原始策略
2. Improve 模式 (iteration 1+): Analyst-First + Pre-Backtest 循环
"""

from typing import Literal

from langgraph.graph import END, StateGraph

from ...core.state import SingleIterationState
from .iteration_nodes import (
    submit_baseline_backtest_node,
    analyst_diagnose_node,
    engineer_modify_node,
    analyst_review_code_node,
    submit_backtest_node,
    wait_for_result_node,
    compare_results_node,
    decide_next_node,
)


def route_by_mode(state: SingleIterationState) -> str:
    """根据模式路由到不同的流程."""
    mode = state.get("mode", "improve")
    if mode == "baseline":
        return "baseline"
    return "improve"


def route_after_wait(state: SingleIterationState) -> str:
    """等待结果后的路由."""
    mode = state.get("mode", "improve")
    if mode == "baseline":
        return "end"  # Baseline 直接结束
    return "compare"  # Improve 继续对比


def route_after_diagnose(state: SingleIterationState) -> str:
    """诊断后的路由 - 检查是否需要终止."""
    if state.get("should_terminate"):
        return "end"
    return "continue"


def route_after_code_review(state: SingleIterationState) -> str:
    """代码审核后的路由 - Pre-Backtest 循环的关键决策点."""
    if state.get("code_review_passed", False):
        return "submit"

    code_iter = state.get("code_iteration_count", 0)
    max_code_iter = state.get("max_code_iterations", 3)

    if code_iter >= max_code_iter:
        return "submit"  # 达到最大次数，强制提交

    return "retry"  # 继续 Pre-Backtest 循环


def create_single_iteration_graph() -> StateGraph:
    """创建支持 Baseline + Analyst-First + Pre-Backtest 循环的图.

    流程:

    Baseline 模式 (iteration 0):
        submit_baseline_backtest -> wait_for_result -> END

    Improve 模式 (iteration 1+):
        ┌─────────────────────────────────────────┐
        │ Pre-Backtest 循环                        │
        │   analyst_diagnose -> engineer_modify   │
        │        -> analyst_review_code           │
        │        -> [条件路由]                     │
        │           ├─ pass/max -> submit_backtest│
        │           └─ fail -> analyst_diagnose   │
        └─────────────────────────────────────────┘
        -> wait_for_result -> compare_results -> decide_next -> END
    """
    workflow = StateGraph(SingleIterationState)

    # === Baseline 节点 ===
    workflow.add_node("submit_baseline_backtest", submit_baseline_backtest_node)

    # === Pre-Backtest 循环节点 ===
    workflow.add_node("analyst_diagnose", analyst_diagnose_node)
    workflow.add_node("engineer_modify", engineer_modify_node)
    workflow.add_node("analyst_review_code", analyst_review_code_node)

    # === 共享节点 ===
    workflow.add_node("submit_backtest", submit_backtest_node)
    workflow.add_node("wait_for_result", wait_for_result_node)
    workflow.add_node("compare_results", compare_results_node)
    workflow.add_node("decide_next", decide_next_node)

    # === 入口路由 ===
    workflow.set_conditional_entry_point(
        route_by_mode,
        {
            "baseline": "submit_baseline_backtest",
            "improve": "analyst_diagnose",
        }
    )

    # === Baseline 流程 ===
    workflow.add_edge("submit_baseline_backtest", "wait_for_result")

    # === Pre-Backtest 循环流程 ===
    # 诊断后检查是否需要终止 (如没有数据可诊断)
    workflow.add_conditional_edges(
        "analyst_diagnose",
        route_after_diagnose,
        {
            "continue": "engineer_modify",
            "end": END,  # 终止 (无数据可诊断)
        }
    )
    workflow.add_edge("engineer_modify", "analyst_review_code")

    # Pre-Backtest 循环条件路由
    workflow.add_conditional_edges(
        "analyst_review_code",
        route_after_code_review,
        {
            "submit": "submit_backtest",
            "retry": "analyst_diagnose",  # 循环回去
        }
    )

    workflow.add_edge("submit_backtest", "wait_for_result")

    # === wait_for_result 后的路由 ===
    workflow.add_conditional_edges(
        "wait_for_result",
        route_after_wait,
        {
            "end": END,  # Baseline 直接结束
            "compare": "compare_results",  # Improve 继续
        }
    )

    # === 最终流程 ===
    workflow.add_edge("compare_results", "decide_next")
    workflow.add_edge("decide_next", END)

    return workflow.compile()
