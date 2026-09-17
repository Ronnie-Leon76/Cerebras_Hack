from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from .crew import run_account_prep
from .models import AccountPrepResult


class PrepState(TypedDict, total=False):
    account: dict
    result: dict
    error: str


def _run(state: PrepState) -> PrepState:
    account = state["account"]
    result: AccountPrepResult = run_account_prep(account)
    return {"account": account, "result": result.model_dump()}


def build_graph():
    g = StateGraph(PrepState)
    g.add_node("account_prep_crew", _run)
    g.add_edge(START, "account_prep_crew")
    g.add_edge("account_prep_crew", END)
    return g.compile()


_GRAPH = None


def invoke_prep(account: dict) -> AccountPrepResult:
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    out = _GRAPH.invoke({"account": account})
    if out.get("result"):
        return AccountPrepResult.model_validate(out["result"])
    return AccountPrepResult(account_id=account.get("id") or "", error=out.get("error") or "empty")
