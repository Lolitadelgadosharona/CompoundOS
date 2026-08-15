"""Investment Committee Decision Lifecycle — Sprint 013 Slice D.

Committee integration, Owner decision, journaling, learning loop.
Completes the full AI → Committee → Owner → Journal → Learning chain.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session


def _symbol_for_run(session: Session, run_id: UUID) -> str:
    """Derive the investment symbol from the research run's FK chain.

    research_runs → research_requests → committee_review_requests →
    investment_ideas (title holds the symbol).
    """
    row = session.execute(
        text(
            "SELECT i.title FROM research_runs rr"
            " JOIN research_requests rq ON rq.id = rr.request_id"
            " JOIN committee_review_requests cr ON cr.id = rq.review_request_id"
            " JOIN investment_ideas i ON i.id = cr.investment_idea_id"
            " WHERE rr.id = :rid"
        ),
        {"rid": run_id},
    ).fetchone()
    return row[0] if row else "unknown"

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
                    " title, proposal_text, status,"
                    " created_at, updated_at)"
                    " VALUES (:id, :hid, 'AI Research Review',"
                    " 'Automated AI research has been completed.',"
                    " :st, NOW(), NOW())"
                ),
                {"id": session_id, "hid": household_id,
                 "st": "draft"},
            )
            session.flush()

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
                        " VALUES (:id, :sid, 'decision',"
                        " 'AI Research Memo', :ch, 'ai_generated',"
                        " :content, NOW(), '0.95', 'medium', 'cmte_v1',"
                        " NOW())" 
                    ),
                    {
                        "id": uuid4(), "sid": session_id,
                        "ch": str(uuid4()),
                        "content": json.dumps({
                            "memo_id": str(memo_row[0]),
                            "run_id": str(run_id),
                            "symbol": _symbol_for_run(session, run_id),
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


class DecisionBridgeService:
    """Committee outcome → Decision Journal draft (minimal mapping).

    Reuses services/decisions.py (create_decision + update_draft). Never
    inserts bare `decisions` rows — the journal owns the lifecycle.
    """

    @staticmethod
    def create_decision_draft(
        session: Session,
        run_id: UUID,
        symbol: str,
        recommendation: str,
        thesis: str,
        risks: list,
    ) -> tuple:
        """Create a Decision + Draft via the journal (status='draft').

        Minimal mapping:
          title                 -> "{symbol} investment decision"
          decision_summary      -> committee recommendation
          rationale             -> memo thesis
          risks_and_uncertainties -> memo risk factors (JSON)
          evidence_or_sources   -> research_run_id (provenance source)
        """
        from apps.api.decision_schemas import (
            CreateDecisionRequest,
            UpdateDecisionDraftRequest,
        )
        from apps.api.services.decisions import create_decision, update_draft

        title = f"{symbol} investment decision"
        decision, draft = create_decision(
            session, CreateDecisionRequest(title=title),
        )
        payload = UpdateDecisionDraftRequest(
            expected_revision=draft.revision,
            decision_summary=f"Committee recommendation: {recommendation}",
            rationale=thesis or f"{symbol} research thesis",
            risks_and_uncertainties=json.dumps(risks) if risks else None,
            evidence_or_sources=f"research_run_id={run_id}",
            decision_date=date.today(),
        )
        draft = update_draft(session, decision.id, payload)
        return decision, draft


class OwnerDecisionService:
    """Owner approve/reject with full journal lifecycle.

    AI CANNOT call these methods — they require Owner authentication
    enforced by API auth middleware (Sprint 010-D). Approval flows
    through the Decision Journal (draft → confirm → snapshot), never
    bare `decisions` rows.
    """

    @staticmethod
    def approve(session: Session, idea_id: UUID, memo_id: UUID,
                session_id: UUID, confidence: int,
                household_id: UUID | None = None,
                rationale: str = "") -> dict:
        from apps.api.decision_schemas import ConfirmDecisionRequest
        from apps.api.services.decisions import confirm_draft

        memo = OwnerDecisionService._load_memo(session, memo_id)
        run_id = memo["run_id"]
        symbol = _symbol_for_run(session, run_id)

        # Journal: create draft (minimal mapping)
        decision, draft = DecisionBridgeService.create_decision_draft(
            session, run_id, symbol, memo["recommendation"],
            memo["thesis"], memo["risks"],
        )

        # Owner approval: confirm → confirmed snapshot
        confirm_draft(session, decision.id, ConfirmDecisionRequest(
            expected_revision=draft.revision, confirmation=True,
        ))

        # Learning: schedule reviews (30/90/365 days)
        review_ids = LearningLoopService.schedule_reviews(
            session, decision.id,
        )

        OwnerDecisionService._audit(session, "investment_decision",
                                    "approved", str(decision.id))
        return {
            "decision_id": str(decision.id),
            "status": "approved",
            "review_ids": [str(r) for r in review_ids],
        }

    @staticmethod
    def reject(session: Session, idea_id: UUID, memo_id: UUID,
               session_id: UUID, confidence: int,
               household_id: UUID | None = None,
               rationale: str = "") -> dict:
        memo = OwnerDecisionService._load_memo(session, memo_id)
        run_id = memo["run_id"]
        symbol = _symbol_for_run(session, run_id)

        # Journal: create a draft record but do NOT confirm (no decision)
        decision, _draft = DecisionBridgeService.create_decision_draft(
            session, run_id, symbol, memo["recommendation"],
            memo["thesis"], memo["risks"],
        )

        OwnerDecisionService._audit(session, "investment_decision",
                                    "rejected", str(decision.id))
        return {"decision_id": str(decision.id), "status": "rejected"}

    @staticmethod
    def confirm_decision(session: Session, decision_id: UUID) -> dict:
        """Owner confirms an EXISTING decision draft (journal confirm).

        The draft is created by the research worker (DecisionBridgeService);
        this action is the Owner's approval → confirmed snapshot + learning
        reviews. Requires Owner authentication (API middleware).
        """
        from apps.api.decision_schemas import ConfirmDecisionRequest
        from apps.api.services.decisions import confirm_draft, read_draft

        draft = read_draft(session, decision_id)
        confirm_draft(session, decision_id, ConfirmDecisionRequest(
            expected_revision=draft.revision, confirmation=True,
        ))
        review_ids = LearningLoopService.schedule_reviews(
            session, decision_id,
        )
        OwnerDecisionService._audit(session, "investment_decision",
                                    "approved", str(decision_id))
        return {
            "decision_id": str(decision_id),
            "status": "approved",
            "review_ids": [str(r) for r in review_ids],
        }

    @staticmethod
    def reject_decision(session: Session, decision_id: UUID) -> dict:
        """Owner rejects an EXISTING decision draft (journal discard).

        Removes the pending draft — no decision is made. Requires Owner
        authentication (API middleware).
        """
        from apps.api.decision_schemas import DiscardDecisionRequest
        from apps.api.services.decisions import discard_draft, read_draft

        draft = read_draft(session, decision_id)
        discard_draft(session, decision_id, DiscardDecisionRequest(
            expected_revision=draft.revision,
        ))
        OwnerDecisionService._audit(session, "investment_decision",
                                    "rejected", str(decision_id))
        return {"decision_id": str(decision_id), "status": "rejected"}

    @staticmethod
    def _load_memo(session: Session, memo_id: UUID) -> dict:
        memo = session.execute(
            text(
                "SELECT memo, recommendation, run_id FROM investment_memos"
                " WHERE id = :id"
            ),
            {"id": memo_id},
        ).fetchone()
        if memo is None:
            raise ValueError("No memo found for decision")
        memo_json = (memo[0] if isinstance(memo[0], dict)
                     else json.loads(memo[0]))
        return {
            "thesis": memo_json.get("thesis", ""),
            "risks": memo_json.get("risks", []),
            "recommendation": memo[1] or "HOLD",
            "run_id": memo[2],
        }

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

    REVIEW_INTERVALS = [30, 90, 365]  # 365 maps to 1_year

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
                    " (id, decision_id, review_type, scheduled_at,"
                    " created_at)"
                    " VALUES (:id, :did, :rt, :sd, NOW())" 
                ),
                {
                    "id": rid, "did": decision_id,
                    "rt": "1_year" if days == 365 else f"{days}_day",
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
    """Traces full provenance: Decision → Draft → Memo → Perspectives
    → LLM Execution → Evidence."""

    @staticmethod
    def trace(session: Session, decision_id: UUID) -> dict:
        dec = session.execute(
            text("SELECT id, status FROM decisions WHERE id = :id"),
            {"id": decision_id},
        ).fetchone()
        if dec is None:
            return {"error": "Decision not found"}

        chain: dict = {"decision": {"id": str(dec[0]), "status": dec[1]}}

        # Decision Draft (content preserved in the confirmed snapshot after
        # confirm deletes the draft row).
        run_id: Optional[UUID] = None
        row = session.execute(
            text(
                "SELECT id, title, rationale, evidence_or_sources"
                " FROM decision_drafts WHERE decision_id = :id"
            ),
            {"id": decision_id},
        ).fetchone()
        confirmed = False
        if row is None:
            row = session.execute(
                text(
                    "SELECT id, title, rationale, evidence_or_sources"
                    " FROM decision_confirmed_snapshots"
                    " WHERE decision_id = :id"
                ),
                {"id": decision_id},
            ).fetchone()
            confirmed = row is not None
        if row is not None:
            chain["decision_draft"] = {
                "id": str(row[0]), "title": row[1],
                "rationale": row[2], "source": row[3],
                "confirmed": confirmed,
            }
            run_id = ProvenanceService._parse_run_id(row[3])

        if run_id is None:
            return chain

        # Investment Memo
        memo = session.execute(
            text(
                "SELECT id, confidence_score, recommendation"
                " FROM investment_memos WHERE run_id = :rid"
            ),
            {"rid": run_id},
        ).fetchone()
        if memo is None:
            return chain
        chain["memo"] = {
            "id": str(memo[0]), "confidence": memo[1],
            "recommendation": memo[2],
        }

        # Perspective Analyses
        perspectives = session.execute(
            text(
                "SELECT perspective, model, conviction_score"
                " FROM perspective_analyses WHERE run_id = :rid"
                " ORDER BY created_at"
            ),
            {"rid": run_id},
        ).fetchall()
        chain["perspectives"] = [
            {"perspective": p[0], "model": p[1], "conviction": p[2]}
            for p in perspectives
        ]

        # LLM Execution
        llm = session.execute(
            text(
                "SELECT perspective, model, status, input_tokens,"
                " output_tokens FROM llm_execution_log"
                " WHERE run_id = :rid ORDER BY created_at"
            ),
            {"rid": run_id},
        ).fetchall()
        chain["llm_execution"] = [
            {"perspective": e[0], "model": e[1], "status": e[2],
             "input_tokens": e[3], "output_tokens": e[4]}
            for e in llm
        ]

        # Evidence (committee evidence items linked to the memo)
        evidence = session.execute(
            text(
                "SELECT source_title, provenance FROM committee_evidence_items"
                " WHERE structured_facts->>'memo_id' = :mid"
            ),
            {"mid": str(memo[0])},
        ).fetchall()
        chain["evidence"] = [
            {"source_title": e[0], "provenance": e[1]} for e in evidence
        ]

        return chain

    @staticmethod
    def _parse_run_id(source: Optional[str]) -> Optional[UUID]:
        if not source:
            return None
        marker = "research_run_id="
        if marker in source:
            try:
                return UUID(source.split(marker, 1)[1].strip())
            except ValueError:
                return None
        return None
