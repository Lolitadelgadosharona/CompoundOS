"""PermissionGate — explicit authorization boundary (M6-004 Slice A).

Central policy mapping action → allowed callers. Fail-closed: any
unknown action or unauthorized caller is DENIED. Wired into
GovernedLLMExecutor so every LLM execution passes an explicit
authorization check.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class PermissionResult:
    allowed: bool
    reason: str = ""


class PermissionGate:
    """Enforces the action→callers policy. Fail-closed by default."""

    # "ai" is the sanctioned research pipeline (the only autonomous
    # caller); "owner" is the human Owner (key-authenticated). Any other
    # caller is denied.
    DEFAULT_POLICY: dict[str, set[str]] = {
        "execute_llm_call": {"owner", "ai"},
    }

    def __init__(self, policy: Optional[dict] = None):
        self._policy = policy or self.DEFAULT_POLICY

    def check(self, action: str, caller: str) -> PermissionResult:
        allowed_callers = self._policy.get(action)
        if allowed_callers is None:
            return PermissionResult(
                allowed=False, reason=f"Unknown action: {action}",
            )
        if caller not in allowed_callers:
            return PermissionResult(
                allowed=False,
                reason=f"Caller '{caller}' not authorized for '{action}'",
            )
        return PermissionResult(allowed=True)
