"""M7-002 tests — deployment config static validation.

These are file-parse tests (no DB, no AI) that guard the deployment
artifacts: .env.example, entrypoint.sh, and the first-key bootstrap.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_ENV_KEYS = [
    "ENVIRONMENT", "DATABASE_URL", "DB_PASSWORD",
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "AV_API_KEY",
    "REDIS_URL", "CADDY_DOMAIN",
]


class TestEnvExample:
    def test_contains_required_keys(self):
        content = (REPO_ROOT / ".env.example").read_text()
        for key in REQUIRED_ENV_KEYS:
            assert key in content, f".env.example missing {key}"

    def test_placeholders_only_no_secrets(self):
        content = (REPO_ROOT / ".env.example").read_text()
        # placeholder marker present
        assert "CHANGE_ME" in content
        # secret key lines are blank (no real values assigned)
        for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "AV_API_KEY",
                    "GOOGLE_API_KEY", "ANTHROPIC_AUTH_TOKEN", "DB_PASSWORD"):
            for line in content.splitlines():
                line = line.strip()
                if line.startswith(key + "="):
                    value = line.split("=", 1)[1]
                    assert value in ("", "CHANGE_ME"), \
                        f"{key} has a real value: {value!r}"


class TestEntrypoint:
    def test_migrates_before_start(self):
        content = (REPO_ROOT / "scripts" / "entrypoint.sh").read_text()
        assert "alembic upgrade head" in content
        assert "exec uvicorn" in content
        assert content.index("alembic upgrade head") < content.index(
            "exec uvicorn")

    def test_fails_closed(self):
        content = (REPO_ROOT / "scripts" / "entrypoint.sh").read_text()
        assert "set -eu" in content
        assert "exit 1" in content


class TestBootstrapKey:
    def test_first_key_guard(self):
        content = (REPO_ROOT / "apps" / "api" / "bootstrap_key.py").read_text()
        assert "SELECT COUNT(*) FROM owner_api_keys" in content
        assert "refusing" in content.lower()

    def test_no_environment_gate(self):
        content = (REPO_ROOT / "apps" / "api" / "bootstrap_key.py").read_text()
        assert "requires ENVIRONMENT" not in content
