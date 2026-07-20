"""Sprint 006 Slice B — LLM API credential management.

macOS Keychain primary; explicit environment variable fallback.
Plaintext config files are FORBIDDEN.
"""

from __future__ import annotations

import os
from typing import Optional


class CredentialError(Exception):
    """Raised when credentials cannot be retrieved."""


def get_api_key(provider: str) -> str:
    """Retrieve API key for an LLM provider.

    Priority:
      1. macOS Keychain (service: compoundos-<provider>)
      2. Environment variable (COMPOUNDOS_<PROVIDER>_API_KEY)
         — ONLY when COMPOUNDOS_ALLOW_ENV_CREDENTIALS=1 is explicitly set
      3. Nothing — raise CredentialError

    Plaintext config files are NEVER used.
    """
    key = _from_keychain(provider)
    if key:
        return key

    key = _from_env(provider)
    if key:
        return key

    raise CredentialError(
        f"No API key found for provider '{provider}'."
        f" Store it in macOS Keychain (service: compoundos-{provider})"
        f" or set COMPOUNDOS_{provider.upper()}_API_KEY"
        f" with COMPOUNDOS_ALLOW_ENV_CREDENTIALS=1."
    )


def credential_available(provider: str) -> bool:
    """Check if credentials are available without raising."""
    try:
        get_api_key(provider)
        return True
    except CredentialError:
        return False


def _from_keychain(provider: str) -> Optional[str]:
    """Retrieve API key from macOS Keychain."""
    import subprocess
    try:
        result = subprocess.run(
            [
                "security", "find-generic-password",
                "-s", f"compoundos-{provider}",
                "-a", "compoundos",
                "-w",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None


def _from_env(provider: str) -> Optional[str]:
    """Retrieve API key from environment variable.

    Only allowed when COMPOUNDOS_ALLOW_ENV_CREDENTIALS=1 is explicitly set.
    This prevents accidental credential exposure through process listings.
    """
    allowed = os.environ.get("COMPOUNDOS_ALLOW_ENV_CREDENTIALS", "").strip()
    if allowed != "1":
        return None
    env_var = f"COMPOUNDOS_{provider.upper()}_API_KEY"
    return os.environ.get(env_var, "").strip() or None
