"""M6-004 Slice A tests — PermissionGate (fail-closed authorization)."""

from apps.api.services.permission_gate import PermissionGate


class TestPermissionGate:
    def test_owner_allowed(self):
        gate = PermissionGate()
        result = gate.check("execute_llm_call", "owner")
        assert result.allowed is True

    def test_ai_allowed(self):
        gate = PermissionGate()
        result = gate.check("execute_llm_call", "ai")
        assert result.allowed is True

    def test_unknown_caller_denied(self):
        gate = PermissionGate()
        result = gate.check("execute_llm_call", "hacker")
        assert result.allowed is False
        assert "not authorized" in result.reason

    def test_unknown_action_denied(self):
        gate = PermissionGate()
        result = gate.check("execute_trade", "owner")
        assert result.allowed is False
        assert "Unknown action" in result.reason
