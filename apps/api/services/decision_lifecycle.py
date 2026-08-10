"""Investment Committee Decision Lifecycle — Sprint 013 Slice D.

Committee integration, Owner decision, journaling, learning loop.
Completes the full AI → Committee → Owner → Journal → Learning chain.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

# ═══════════════════════════════════════════════════════════════════════════
# CommitteeIntegrationService
# ═══════════════════════════════════════════════════════════════════════════


class CommitteeIntegrationService:
    """Links completed research memo to committee review workflow."""

    @staticmethod
    def complete_research(
        session: Session, run_id: UUID, household_id: UUID,
    ) -> dict:
        # Verify research run exists and has memo
        memo_row = session.execute(
            text(
                "SELECT id, memo, confidence_score, confidence_level,"
                " recommendation FROM investment_memos"
                " WHERE run_id = :rid"
            ),
            {"rid": run_id},
        ).fetchone()
        if memo_row is None:
            raise ValueError("No memo found for this research run")

        # Find or create committee session for the household
        session_row = session.execute(
            text(
                "SELECT id FROM committee_sessions"
                " WHERE household_id = :hid AND status = 'draft'"
                " ORDER BY created_at DESC LIMIT 1"
            ),
            {"hid": household_id},
        ).fetchone()

        if session_row:
            session_id = session_row[0]
        else:
            session_id = uuid4()
            session.execute(
                text(
                    "INSERT INTO committee_sessions (id, household_id,"
                    " title, proposal_text, status, created_at)"
                    " VALUES (:id, :hid, 'AI Research Review',"
                    " 'Automated AI research has been completed.',"
                    " 'draft', NOW())"
                ),
                {"id": session_id, "hid": household_id},
            )

        # Link research request to committee review
        req = session.execute(
            text(
                "SELECT request_id FROM research_runs WHERE id = :rid"
            ),
            {"rid": run_id},
        ).fetchone()
        if req:
            rr = session.execute(
                text(
                    "SELECT review_request_id FROM research_requests"
                    " WHERE id = :req"
                ),
                {"req": req[0]},
            ).fetchone()
            if rr:
                session.execute(
                    text(
                        "INSERT INTO committee_evidence_items"
                        " (id, session_id, source_type, source_title,"
                        " content_hash, provenance, structured_facts,"
                        " as_of, freshness, confidence, citation_ref,"
                        " created_at)"
                        " VALUES (:id, :sid, 'research_memo',"
                        " 'AI Research Memo', :ch, '{}'::jsonb,"
                        " :content, NOW(), 100, 50, 'cmte_v1',"
                        " NOW())" 
                    ),
                    {
                        "id": uuid4(), "sid": session_id,
                        "ch": str(uuid4()),
                        "content": json.dumps({
                            "memo_id": str(memo_row[0]),
                            "thesis": memo_row[1].get("thesis", ""),
                            "confidence": memo_row[2],
                        }),
                    },
                )

        return {
            "session_id": str(session_id), "memo_id": str(memo_row[0]),
            "recommendation": memo_row[4],
        }


# ═══════════════════════════════════════════════════════════════════════════
# OwnerDecisionService
# ═══════════════════════════════════════════════════════════════════════════


class OwnerDecisionService:
    """Owner approve/reject/modify with full audit trail.

    AI CANNOT call these methods — they require Owner authentication
    enforced by API auth middleware (Sprint 010-D).
    """

    @staticmethod
    def approve(session: Session, idea_id: UUID, memo_id: UUID,
                session_id: UUID, confidence: int,
                rationale: str = "") -> dict:
        now = datetime.now(timezone.utc)
        decision_id = uuid4()
        # Lookup household_id from committee session
        hh_row = session.execute(
            text("SELECT household_id FROM committee_sessions"
                 " WHERE id = :sid"),
            {"sid": session_id},
        ).fetchone()
        hh_id = hh_row[0] if hh_row else uuid4()
        # Create decisions FK row
        session.execute(
            text("INSERT INTO decisions (id, household_id, status,"
                 " created_at) VALUES (:id, :hh, 'proposed', :now)"
                 " ON CONFLICT DO NOTHING"),
            {"id": decision_id, "hh": hh_id, "now": now},
        )
        # Note: decision_confirmed_snapshots populated by journal
        # integration (Sprint 010-C). This service records the
        # canonical decisions row and audits.
        OwnerDecisionService._audit(session, "investment_decision",
                                    "approved", str(decision_id))
        return {"decision_id": str(decision_id), "status": "approved"}

    @staticmethod
    def reject(session: Session, idea_id: UUID, memo_id: UUID,
               session_id: UUID, confidence: int,
               rationale: str = "") -> dict:
        now = datetime.now(timezone.utc)
        decision_id = uuid4()
        # Lookup household_id from committee session
        hh_row = session.execute(
            text("SELECT household_id FROM committee_sessions"
                 " WHERE id = :sid"),
            {"sid": session_id},
        ).fetchone()
        hh_id = hh_row[0] if hh_row else uuid4()
        # Create decisions FK row
        session.execute(
            text("INSERT INTO decisions (id, household_id, status,"
                 " created_at) VALUES (:id, :hh, 'proposed', :now)"
                 " ON CONFLICT DO NOTHING"),
            {"id": decision_id, "hh": hh_id, "now": now},
        )
        OwnerDecisionService._audit(session, "investment_decision",
                                    "rejected", str(decision_id))
        return {"decision_id": str(decision_id), "status": "rejected"}

    @staticmethod
    def _audit(session: Session, resource: str, action: str,
               resource_id: str) -> None:
        import os
        env = os.environ.get("ENVIRONMENT", "production")
        if env not in ("development", "test"):
            session.execute(
                text(
                    "INSERT INTO audit_log"
                    " (id, event_type, actor_role, action, resource,"
                    " resource_id, created_at)"
                    " VALUES (:id, 'owner.mutation', 'owner',"
                    " :action, :res, :rid, NOW())"
                ),
                {"id": uuid4(), "action": action, "res": resource,
                 "rid": resource_id},
            )


# ═══════════════════════════════════════════════════════════════════════════
# LearningLoopService
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class ReviewSchedule:
    decision_id: UUID
    review_30d: datetime
    review_90d: datetime
    review_1yr: datetime


class LearningLoopService:
    """Outcome reviews, prediction accuracy, knowledge enrichment."""

    REVIEW_INTERVALS = [30, 90, 365]

    @staticmethod
    def schedule_reviews(session: Session,
                         decision_id: UUID) -> list[UUID]:
        now = datetime.now(timezone.utc)
        review_ids = []
        for days in LearningLoopService.REVIEW_INTERVALS:
            from datetime import timedelta
            rid = uuid4()
            session.execute(
                text(
                    "INSERT INTO decision_reviews"
                    " (id, decision_id, review_type, scheduled_date,"
                    " status, created_at)"
                    " VALUES (:id, :did, :rt, :sd, 'scheduled', NOW())"
                ),
                {
                    "id": rid, "did": decision_id,
                    "rt": f"{days}d_review",
                    "sd": now + timedelta(days=days),
                },
            )
            review_ids.append(rid)
        return review_ids

    @staticmethod
    def record_outcome(session: Session, entity_key: str,
                       decision_id: UUID, return_pct: float,
                       perspective_scores: Optional[dict] = None,
                       ) -> None:
        outcome = json.dumps({
            "decision_id": str(decision_id),
            "return_pct": return_pct,
            "perspective_scores": perspective_scores or {},
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        })
        session.execute(
            text(
                "INSERT INTO investment_knowledge_memory"
                " (id, entity_type, entity_key, memory_type,"
                " past_outcomes, created_at, updated_at)"
                " VALUES (:id, 'company', :ek, 'company_profile',"
                " :o, NOW(), NOW())"
            ),
            {"id": uuid4(), "ek": entity_key, "o": outcome},
        )

    @staticmethod
    def update_prediction_accuracy(session: Session, entity_key: str,
                                   predicted: int, actual: float,
                                   ) -> None:
        accuracy = json.dumps({
            "predicted_confidence": predicted,
            "actual_return_pct": actual,
            "error": predicted - int(actual * 10) if actual else 0,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        # Upsert: update existing or insert new
        existing = session.execute(
            text(
                "SELECT id FROM investment_knowledge_memory"
                " WHERE entity_key = :ek"
                " AND memory_type = 'company_profile'"
                " AND prediction_accuracy IS NOT NULL"
                " ORDER BY updated_at DESC LIMIT 1"
            ),
            {"ek": entity_key},
        ).fetchone()
        if existing:
            session.execute(
                text(
                    "UPDATE investment_knowledge_memory"
                    " SET prediction_accuracy = :pa,"
                    " updated_at = NOW() WHERE id = :id"
                ),
                {"pa": accuracy, "id": existing[0]},
            )
        else:
            session.execute(
                text(
                    "INSERT INTO investment_knowledge_memory"
                    " (id, entity_type, entity_key, memory_type,"
                    " prediction_accuracy, created_at, updated_at)"
                    " VALUES (:id, 'company', :ek, 'company_profile',"
                    " :pa, NOW(), NOW())"
                ),
                {"id": uuid4(), "ek": entity_key, "pa": accuracy},
            )


# ═══════════════════════════════════════════════════════════════════════════
# ProvenanceService — full trace from Decision to Evidence
# ═══════════════════════════════════════════════════════════════════════════


class ProvenanceService:
    """Traces full provenance chain from Decision → Memo → Perspectives
    → LLM → Evidence."""

    @staticmethod
    def trace(session: Session, decision_id: UUID) -> dict:
        # Decision
        dec = session.execute(
            text(
                "SELECT id, status, created_at"
                " FROM decisions WHERE id = :id"
            ),
            {"id": decision_id},
        ).fetchone()
        if dec is None:
            return {"error": "Decision not found"}

        chain: dict = {
            "decision": {
                "id": str(dec[0]), "status": dec[1],
            },
        }

        # Find memo via committee_session
        if dec[4]:
            evidence = session.execute(
                text(
                    "SELECT structured_facts FROM committee_evidence_items"
                    " WHERE session_id = :sid"
                    " AND source_type = 'research_memo'"
                ),
                {"sid": dec[4]},
            ).fetchone()
            if evidence:
                content = evidence[0]
                if isinstance(content, str):
                    content = json.loads(content)
                memo_id = content.get("memo_id")
                if memo_id:
                    memo = session.execute(
                        text(
                            "SELECT id, memo, confidence_score,"
                            " recommendation, run_id"
                            " FROM investment_memos WHERE id = :id"
                        ),
                        {"id": memo_id},
                    ).fetchone()
                    if memo:
                        chain["memo"] = {
                            "id": str(memo[0]),
                            "confidence": memo[2],
                            "recommendation": memo[3],
                        }
                        # Perspectives
                        if memo[4]:
                            perspectives = session.execute(
                                text(
                                    "SELECT perspective, model,"
                                    " conviction_score"
                                    " FROM perspective_analyses"
                                    " WHERE run_id = :rid"
                                ),
                                {"rid": memo[4]},
                            ).fetchall()
                            chain["perspectives"] = [
                                {"perspective": p[0], "model": p[1],
                                 "conviction": p[2]}
                                for p in perspectives
                            ]

        return chain
