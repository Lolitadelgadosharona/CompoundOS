"""Tests for Sprint 014 Slice B — Owner Dashboard."""

from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


class TestDashboardRoutes:
    def test_dashboard_loads(self):
        r = client.get("/dashboard")
        assert r.status_code == 200
        assert "Dashboard" in r.text
        assert "$1,250,000" in r.text

    def test_research_loads(self):
        r = client.get("/research")
        assert r.status_code == 200
        assert "Research" in r.text

    def test_memo_loads(self):
        r = client.get("/memo/test-id")
        assert r.status_code == 200
        assert "Investment Memo" in r.text
        assert "BUY" in r.text

    def test_decisions_loads(self):
        r = client.get("/decisions")
        assert r.status_code == 200
        assert "Committee Decisions" in r.text

    def test_learning_loads(self):
        r = client.get("/learning")
        assert r.status_code == 200
        assert "Learning Dashboard" in r.text
        assert "perspective" in r.text.lower()


class TestDashboardAuth:
    def test_dashboard_no_auth_in_dev(self):
        """In development/test, dashboard is accessible without API key."""
        r = client.get("/dashboard")
        assert r.status_code == 200


class TestDashboardStructure:
    def test_navigation_present(self):
        """All pages have the nav bar."""
        for path in ["/dashboard", "/research", "/decisions",
                     "/learning"]:
            r = client.get(path)
            assert "CompoundOS" in r.text

    def test_no_trading_interface(self):
        """Dashboard has no trade/broker buttons."""
        for path in ["/dashboard", "/research", "/decisions",
                     "/learning"]:
            r = client.get(path)
            assert "trade" not in r.text.lower()
            assert "broker" not in r.text.lower()
            assert "execute" not in r.text.lower()

    def test_html_renders(self):
        """All pages return HTML content type."""
        for path in ["/dashboard", "/research", "/memo/test",
                     "/decisions", "/learning"]:
            r = client.get(path)
            assert "text/html" in r.headers["content-type"]
