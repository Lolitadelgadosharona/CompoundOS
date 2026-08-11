"""Scale Intelligence API — Sprint 022."""

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from apps.api.services.scale_intelligence import (
    AdvancedCommittee,
    FamilyOfficeService,
    GraphEdge,
    GraphNode,
    KnowledgeGraph,
    Portfolio,
    PortfolioMonitor,
)

router = APIRouter(prefix="/api/scale", tags=["scale-intelligence"])


# ── Knowledge Graph ──────────────────────────────────────────────────


class AddNodeRequest(BaseModel):
    node_id: str
    node_type: str
    label: str
    properties: dict = {}


@router.post("/graph/node")
def add_node(body: AddNodeRequest):
    node = GraphNode(body.node_id, body.node_type,
                     body.label, body.properties)
    KnowledgeGraph.add_node(node)
    return {"added": node.node_id, "stats": KnowledgeGraph.stats()}


class AddEdgeRequest(BaseModel):
    source_id: str
    target_id: str
    edge_type: str


@router.post("/graph/edge")
def add_edge(body: AddEdgeRequest):
    edge = GraphEdge(body.source_id, body.target_id,
                     body.edge_type)
    KnowledgeGraph.add_edge(edge)
    return {"added": True, "stats": KnowledgeGraph.stats()}


@router.get("/graph/stats")
def graph_stats():
    return KnowledgeGraph.stats()


@router.get("/graph/related/{node_id}")
def related_nodes(node_id: str):
    nodes = KnowledgeGraph.related(node_id)
    return {
        "node_id": node_id,
        "related": [
            {"id": n.node_id, "type": n.node_type,
             "label": n.label}
            for n in nodes
        ],
    }


# ── Advanced Committee ───────────────────────────────────────────────


class CommitteeRequest(BaseModel):
    symbol: str
    votes: list[dict]


@router.post("/committee/convene")
def convene_committee(body: CommitteeRequest):
    result = AdvancedCommittee.convene(body.symbol, body.votes)
    return AdvancedCommittee.compare(result)


# ── Portfolio Monitoring ─────────────────────────────────────────────


class MonitorRequest(BaseModel):
    positions: list[dict]


@router.post("/monitor/scan")
def scan_positions(body: MonitorRequest):
    alerts = PortfolioMonitor.scan(body.positions)
    return {
        "alerts": [
            {"trigger": a.trigger, "symbol": a.symbol,
             "detail": a.detail, "priority": a.priority}
            for a in alerts
        ],
        "summary": PortfolioMonitor.summary(alerts),
    }


# ── Family Office ────────────────────────────────────────────────────


class AuthRequest(BaseModel):
    user_id: str
    role: str
    portfolios: Optional[list[str]] = None


@router.post("/office/auth")
def authorize_user(body: AuthRequest):
    user = FamilyOfficeService.authorize(
        body.user_id, body.role, body.portfolios,
    )
    return {
        "user_id": user.user_id,
        "role": user.role,
        "can_approve": user.can_approve,
        "can_modify_policy": user.can_modify_policy,
        "accessible": user.accessible_portfolios,
    }


class ConsolidateRequest(BaseModel):
    portfolios: list[dict]


@router.post("/office/consolidate")
def consolidate_portfolios(body: ConsolidateRequest):
    portfolios = [
        Portfolio(
            name=p["name"], portfolio_type=p["type"],
            holdings=p.get("holdings", []),
            total_value=sum(
                h["shares"] * h["price"] for h in p.get("holdings", [])
            ),
        )
        for p in body.portfolios
    ]
    return FamilyOfficeService.consolidate(portfolios)
