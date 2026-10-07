# Read-only broker architecture

Status: IMPLEMENTED OFFLINE FOUNDATION; live integration NOT IMPLEMENTED.
Verified base769631a14acf74ff1cee054a2d23ff2ad9718279, Owner authorization Sprint001.

`broker_foundation.py` owns immutable provider-neutral Account/Position/Cash/Transaction/Snapshot/Provenance/SyncRun contracts. BrokerProvider exposes only read_snapshot. Capabilities enumerate four mandatory reads, optional cost-basis read and reserved unavailable order-preview/order-execute/transfer/withdrawal. BrokerConnection rejects reserved capabilities. Real provider classes are intentionally absent rather than fake functioning adapters. Future IBKR/Schwab/Fidelity adapters implement the same protocol; ManualProvider accepts only explicitly MANUAL-provenance supplied snapshots; Manual Portfolio retains its existing import path.

Broker adapter → complete snapshot → validate external IDs/currency/provenance → canonical resolver → isolated staging → future atomic canonical repository → existing valuation/Policy/Guardian. No connection from approval to this boundary. No broker quote becomes market evidence automatically.

Current reference StagingStore is in-memory, synthetic-test-only, not wired to routes, ledger or recommendations. It proves duplicate/failure semantics, not durability, concurrency, authentication or production readiness. No financial threshold/configuration/default was changed. No schema migration. Existing accounts have provider/account references; positions source CHECK currently excludes fidelity and generic BROKER, so direct persistence must not be improvised.

CanonicalResolver calls existing canonical_asset preserving UUID and full venue/currency/provider identity. Incomplete identities remain UNRESOLVED; broker conId/CUSIP/ISIN require a verified crosswalk before creating Instrument, not ticker-only adaptation. BRK.B is preserved. Existing Asset name/UUID/history are not rewritten. Future DB transaction must wrap resolver and acceptance; rollback all mappings when batch validation fails. Current in-memory store cannot rollback a supplied SQL session; caller must own that transaction.

Holdings answer what is owned. Approved investment_configurations answer desired targets. This module never reads/writes strategy or policy. Unknown identities remain visible, never promoted to trusted advice. Dashboard continues existing DEMO behavior; future overview fields must include native ledger/net-worth scope, investability, account provenance, last successful sync and completeness without invented performance.
