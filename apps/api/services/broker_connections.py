"""Read-only connection contract. No V1 network connector or order implementation."""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class AccountReadCapability(str, Enum):
    ACCOUNT_READ = "ACCOUNT_READ"
    POSITIONS_READ = "POSITIONS_READ"
    CASH_READ = "CASH_READ"
    TRANSACTIONS_READ = "TRANSACTIONS_READ"


class FutureOrderCapability(str, Enum):
    """Separate future authorization boundary; never a V1 capability."""

    ORDER_PREVIEW = "ORDER_PREVIEW"
    ORDER_EXECUTE = "ORDER_EXECUTE"
    TRANSFER = "TRANSFER"
    WITHDRAWAL = "WITHDRAWAL"


class BrokerConnectionProvider(Protocol):
    capabilities: frozenset[AccountReadCapability]

    def read_accounts(self): ...
    def read_positions(self): ...
    def read_cash(self): ...
    def read_transactions(self): ...


@dataclass(frozen=True)
class ReadOnlyConnection:
    name: str
    status: str = "NOT_CONNECTED"
    capabilities: tuple[AccountReadCapability, ...] = tuple(AccountReadCapability)

    def __post_init__(self):
        if any(not isinstance(c, AccountReadCapability) for c in self.capabilities):
            raise ValueError("V1 connections cannot authorize order capabilities")


def connection_directory(manual_accounts):
    rows = [
        ReadOnlyConnection(name) for name in ("Interactive Brokers", "Fidelity", "Charles Schwab")
    ]
    return {
        "brokers": [
            {
                "name": r.name,
                "status": r.status,
                "mode": "READ_ONLY",
                "capabilities": [c.value for c in r.capabilities],
                "last_sync": None,
                "accounts_discovered": 0,
                "cash": None,
                "positions": None,
                "data_quality": "UNKNOWN",
                "available": False,
                "external_connection": False,
            }
            for r in rows
        ],
        "manual": {
            "name": "Manual Portfolio",
            "status": "CONNECTED" if manual_accounts else "NOT_CONNECTED",
            "mode": "LOCAL_RECORDS",
            "external_connection": False,
        },
        "credentials_accepted": False,
        "order_execution_supported": False,
    }
