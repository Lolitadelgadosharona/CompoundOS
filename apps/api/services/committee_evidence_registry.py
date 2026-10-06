"""Context-bound immutable evidence registry; models cannot supply or repair market facts."""

import hashlib
import json
from datetime import datetime, timedelta, timezone

TYPES = {
    "portfolio_snapshot",
    "policy_version",
    "guardian_event",
    "decision",
    "owner_claim",
    "external",
}


def evidence_registry(cs):
    registry = {}
    now = datetime.now(timezone.utc)
    for item in cs.evidence_items:
        if (
            item.session_id != cs.id
            or item.source_type not in TYPES
            or not item.citation_ref
            or not item.provenance
            or not item.as_of
            or item.as_of > now
        ):
            raise ValueError("COMMITTEE_EVIDENCE_INVALID: context/provenance/timestamp")
        hashes = {
            hashlib.sha256(
                json.dumps(item.structured_facts, sort_keys=True, default=str, **kwargs).encode()
            ).hexdigest()
            for kwargs in [{}, {"separators": (",", ":")}]
        }
        if item.content_hash not in hashes:
            raise ValueError("COMMITTEE_EVIDENCE_INVALID: changed deterministic facts")
        serialized = json.dumps(item.structured_facts, default=str).lower()
        mode = (
            "SIMULATED"
            if any(x in serialized for x in ["synthetic", "simulation", "fake-model"])
            else "HISTORICAL"
            if (
                item.source_type in {"portfolio_snapshot", "decision"}
                or item.source_type == "external"
                and now - item.as_of > timedelta(hours=24)
            )
            and not item.citation_ref.startswith("contribution:")
            else "CURRENT_INTERNAL"
        )
        claim = "[model inference] Reference supplied evidence"
        if mode == "SIMULATED":
            claim += " [simulated]"
        if mode == "HISTORICAL":
            claim += " [historical]"
        registry[str(item.id)] = {
            "citation_ref": item.citation_ref,
            "mode": mode,
            "claim": claim,
            "source_type": item.source_type,
            "as_of": item.as_of.isoformat(),
        }
    return registry
