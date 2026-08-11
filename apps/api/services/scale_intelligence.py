"""Scale & Intelligence Enhancement — Sprint 022.

Knowledge graph, advanced AI committee, portfolio monitoring,
and family office layer. No trading. Advisory only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

# ═══════════════════════════════════════════════════════════════════════
# Slice A — Investment Knowledge Graph
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class GraphNode:
    node_id: str
    node_type: str  # company | sector | memo | decision
    label: str
    properties: dict = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )


@dataclass
class GraphEdge:
    source_id: str
    target_id: str
    edge_type: str  # BELONGS_TO | ANALYZED_IN | LED_TO | SUPERSEDES
    properties: dict = field(default_factory=dict)


class KnowledgeGraph:
    """Append-only investment knowledge graph. Immutable history."""

    _nodes: dict[str, GraphNode] = {}
    _edges: list[GraphEdge] = []

    @classmethod
    def add_node(cls, node: GraphNode) -> None:
        # Immutable: never overwrite existing nodes
        if node.node_id not in cls._nodes:
            cls._nodes[node.node_id] = node

    @classmethod
    def add_edge(cls, edge: GraphEdge) -> None:
        cls._edges.append(edge)

    @classmethod
    def get_node(cls, node_id: str) -> GraphNode | None:
        return cls._nodes.get(node_id)

    @classmethod
    def edges_from(cls, node_id: str) -> list[GraphEdge]:
        return [e for e in cls._edges if e.source_id == node_id]

    @classmethod
    def edges_to(cls, node_id: str) -> list[GraphEdge]:
        return [e for e in cls._edges if e.target_id == node_id]

    @classmethod
    def related(cls, node_id: str) -> list[GraphNode]:
        edges = cls.edges_from(node_id) + cls.edges_to(node_id)
        ids = {e.target_id if e.source_id == node_id else e.source_id
               for e in edges}
        return [cls._nodes[i] for i in ids if i in cls._nodes]

    @classmethod
    def query_type(cls, node_type: str) -> list[GraphNode]:
        return [n for n in cls._nodes.values()
                if n.node_type == node_type]

    @classmethod
    def stats(cls) -> dict:
        return {
            "nodes": len(cls._nodes),
            "edges": len(cls._edges),
            "by_type": {
                t: sum(1 for n in cls._nodes.values()
                       if n.node_type == t)
                for t in {"company", "sector", "memo", "decision"}
            },
        }


# ═══════════════════════════════════════════════════════════════════════
# Slice B — Advanced AI Committee
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class CommitteeVote:
    perspective: str
    model: str
    vote: str  # BUY | HOLD | PASS
    confidence: int
    rationale: str = ""
    model_weight: float = 1.0


@dataclass
class CommitteeResult:
    symbol: str
    votes: list[CommitteeVote]
    majority_vote: str = ""
    avg_confidence: float = 0.0
    has_divergence: bool = False
    divergence_detail: str = ""

    def __post_init__(self):
        max_conf = max(v.confidence for v in self.votes)
        min_conf = min(v.confidence for v in self.votes)
        self.has_divergence = (max_conf - min_conf) > 20
        if self.has_divergence:
            high = [v for v in self.votes if v.confidence == max_conf]
            low = [v for v in self.votes if v.confidence == min_conf]
            self.divergence_detail = (
                f"Divergence: {high[0].model}/{high[0].perspective}"
                f" ({max_conf}) vs {low[0].model}/{low[0].perspective}"
                f" ({min_conf})"
            )

        buys = sum(1 for v in self.votes if v.vote == "BUY")
        holds = sum(1 for v in self.votes if v.vote == "HOLD")
        self.majority_vote = "BUY" if buys > holds else (
            "HOLD" if holds > 0 else "PASS"
        )
        self.avg_confidence = sum(v.confidence for v in self.votes) / max(len(self.votes), 1)


MODEL_ASSIGNMENTS = {
    "value": "claude",
    "risk": "claude",
    "policy": "claude",
    "growth": "gpt4o",
    "macro": "gpt4o",
    "portfolio_fit": "gemini",
}

PERSPECTIVES = [
    "value", "growth", "risk", "macro", "policy", "portfolio_fit",
]


class AdvancedCommittee:
    """Multi-model AI committee. Never forces consensus."""

    @classmethod
    def convene(cls, symbol: str,
                votes: list[dict]) -> CommitteeResult:
        committee_votes = [
            CommitteeVote(
                perspective=v["perspective"],
                model=MODEL_ASSIGNMENTS.get(v["perspective"], "unknown"),
                vote=v["vote"], confidence=v["confidence"],
                rationale=v.get("rationale", ""),
            )
            for v in votes
        ]
        return CommitteeResult(
            symbol=symbol, votes=committee_votes,
        )

    @classmethod
    def compare(cls, result: CommitteeResult) -> dict:
        by_model: dict[str, list[CommitteeVote]] = {}
        for v in result.votes:
            by_model.setdefault(v.model, []).append(v)
        return {
            "symbol": result.symbol,
            "majority": result.majority_vote,
            "confidence": round(result.avg_confidence),
            "divergence": result.has_divergence,
            "divergence_detail": result.divergence_detail,
            "by_model": {
                m: {
                    "votes": [{"perspective": vv.perspective,
                               "vote": vv.vote,
                               "confidence": vv.confidence}
                              for vv in vs],
                    "avg_confidence": round(
                        sum(vv.confidence for vv in vs)
                        / max(len(vs), 1),
                    ),
                }
                for m, vs in by_model.items()
            },
        }


# ═══════════════════════════════════════════════════════════════════════
# Slice C — Portfolio Monitoring
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class MonitorAlert:
    trigger: str
    symbol: str
    detail: str
    priority: str  # critical | high | medium | low
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )


class PortfolioMonitor:
    """Event monitoring. Alerts only — no automated response."""

    TRIGGERS = {
        "price_shock": "critical",
        "earnings_imminent": "high",
        "research_stale": "high",
        "dividend_announced": "medium",
        "sector_rotation": "medium",
        "news_sentiment": "low",
    }

    @classmethod
    def scan(cls, positions: list[dict]) -> list[MonitorAlert]:
        alerts: list[MonitorAlert] = []
        for pos in positions:
            symbol = pos["symbol"]
            # Price shock (>5% daily move)
            if abs(pos.get("daily_change_pct", 0)) > 5:
                alerts.append(MonitorAlert(
                    trigger="price_shock", symbol=symbol,
                    detail=f"{symbol} moved {pos['daily_change_pct']:+.1f}% today",
                    priority="critical",
                ))
            # Research stale (>90 days)
            if pos.get("days_since_research", 0) > 90:
                alerts.append(MonitorAlert(
                    trigger="research_stale", symbol=symbol,
                    detail=f"{symbol} research is {pos['days_since_research']} days old",
                    priority="high",
                ))
            # Earnings within 7 days
            if pos.get("days_to_earnings", 999) <= 7:
                alerts.append(MonitorAlert(
                    trigger="earnings_imminent", symbol=symbol,
                    detail=f"{symbol} reports earnings in {pos['days_to_earnings']} days",
                    priority="high",
                ))
            # Dividend announced
            if pos.get("dividend_announced"):
                alerts.append(MonitorAlert(
                    trigger="dividend_announced", symbol=symbol,
                    detail=f"{symbol} announced dividend",
                    priority="medium",
                ))
        return sorted(alerts, key=lambda a: (
            {"critical": 0, "high": 1, "medium": 2, "low": 3}[a.priority],
        ))

    @classmethod
    def summary(cls, alerts: list[MonitorAlert]) -> dict:
        by_priority: dict[str, int] = {}
        for a in alerts:
            by_priority[a.priority] = by_priority.get(a.priority, 0) + 1
        return {
            "total": len(alerts),
            "by_priority": by_priority,
            "needs_attention": (
                by_priority.get("critical", 0)
                + by_priority.get("high", 0)
            ) > 0,
        }


# ═══════════════════════════════════════════════════════════════════════
# Slice D — Family Office Layer
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class Portfolio:
    name: str
    portfolio_type: str  # taxable | ira | trust
    holdings: list[dict] = field(default_factory=list)
    total_value: float = 0.0


@dataclass
class UserRole:
    user_id: str
    role: str  # owner | advisor
    accessible_portfolios: list[str] = field(default_factory=list)
    can_approve: bool = False
    can_modify_policy: bool = False


class FamilyOfficeService:
    """Multi-portfolio family office layer."""

    ROLES = {
        "owner": {
            "can_approve": True,
            "can_modify_policy": True,
            "can_execute": False,  # never — no broker
            "description": "Full access. Final authority.",
        },
        "advisor": {
            "can_approve": False,
            "can_modify_policy": False,
            "can_execute": False,
            "description": "Read-only. View portfolios and research.",
        },
    }

    @classmethod
    def authorize(cls, user_id: str, role: str,
                  portfolios: Optional[list[str]] = None,
                  ) -> UserRole:
        perms = cls.ROLES.get(role, cls.ROLES["advisor"])
        return UserRole(
            user_id=user_id, role=role,
            accessible_portfolios=portfolios or ["main"],
            can_approve=perms["can_approve"],
            can_modify_policy=perms["can_modify_policy"],
        )

    @classmethod
    def consolidate(cls, portfolios: list[Portfolio]) -> dict:
        total = sum(p.total_value for p in portfolios)
        return {
            "total_value": total,
            "portfolio_count": len(portfolios),
            "portfolios": [
                {"name": p.name, "type": p.portfolio_type,
                 "value": p.total_value,
                 "holdings": len(p.holdings)}
                for p in portfolios
            ],
        }
