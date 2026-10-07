"""Owner-invoked Paper-only local runner. No login automation or automatic broker reads."""

import argparse
import os
import secrets
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ca-file", required=True)
    parser.add_argument("--paper-account-file", required=True)
    parser.add_argument("--gateway-port", type=int, default=5000)
    args = parser.parse_args()
    ca = Path(args.ca_file).resolve()
    paper_accounts = Path(args.paper_account_file).resolve()
    if not paper_accounts.is_file():
        raise SystemExit("Private Owner-confirmed Paper account reference file required")
    if not ca.is_file() or not 1024 <= args.gateway_port <= 65535:
        raise SystemExit("Valid local gateway CA and nonprivileged port required")
    root = Path(__file__).resolve().parents[1]
    # Read-only permission is opt-in by invoking this script; no secret IBKR input.
    folder = Path.home() / ".local/share/compoundos-ibkr-paper-local"
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(folder, 0o700)
    config = folder / "database.env"
    if not config.exists():
        fd = os.open(config, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write("POSTGRES_PASSWORD=" + secrets.token_hex(24) + "\n")
    os.chmod(config, 0o600)
    pw = dict(line.split("=", 1) for line in config.read_text().splitlines())["POSTGRES_PASSWORD"]
    env = dict(
        os.environ,
        ENVIRONMENT="test",
        COMPOUNDOS_PREVIEW_MODE="true",
        DATABASE_URL="postgresql+psycopg://postgres:"
        + quote(pw, safe="")
        + "@127.0.0.1:55474/compoundos_owner_preview_test",
        REDIS_URL="redis://127.0.0.1:55475/0",
        COMPOUNDOS_IBKR_READ_ENABLED="1",
        COMPOUNDOS_IBKR_ACCOUNT_MODE="PAPER",
        COMPOUNDOS_IBKR_LIVE_READ_AUTHORIZED="0",
        COMPOUNDOS_IBKR_GATEWAY_CA_FILE=str(ca),
        COMPOUNDOS_IBKR_PAPER_ACCOUNT_FILE=str(paper_accounts),
        COMPOUNDOS_IBKR_GATEWAY_URL=f"https://localhost:{args.gateway_port}/v1/api",
        COMPOUNDOS_ALLOW_ENV_CREDENTIALS="0",
        COMPOUNDOS_YAHOO_ACCESS_AUTHORIZED="0",
        API_INTERNAL_URL="http://127.0.0.1:8182",
        NEXT_PUBLIC_COMPOUNDOS_PREVIEW_MODE="true",
    )
    subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            str(config),
            "-p",
            "compoundos-ibkr-paper-local",
            "-f",
            "docker-compose.ibkr-paper-local.yml",
            "up",
            "-d",
            "--wait",
        ],
        cwd=root,
        check=True,
    )
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"], cwd=root, env=env, check=True
    )
    subprocess.run(
        [sys.executable, "-m", "apps.api.services.preview_seed"], cwd=root, env=env, check=True
    )
    subprocess.run(["npm", "run", "build"], cwd=root / "frontend", env=env, check=True)
    children = []
    try:
        children.append(
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "apps.api.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8182",
                ],
                cwd=root,
                env=env,
            )
        )
        children.append(
            subprocess.Popen(
                ["npm", "run", "start", "--", "--hostname", "127.0.0.1", "--port", "3882"],
                cwd=root / "frontend",
                env=env,
                start_new_session=True,
            )
        )
        print("Paper-only local workspace: http://localhost:3882/accounts")
        print(
            "Authenticate in official gateway, then explicitly choose SYNC NOW. "
            "No reads run on startup."
        )
        children[0].wait()
    except KeyboardInterrupt:
        pass
    finally:
        import signal

        for child in children:
            if child.poll() is None:
                if child is children[-1] and len(children) == 2:
                    os.killpg(child.pid, signal.SIGTERM)
                else:
                    child.terminate()
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()


if __name__ == "__main__":
    main()
