"""Build identity comes from immutable build inputs, never a guessed runtime git checkout."""

import os
import re
from datetime import datetime


def build_info():
    sha = os.getenv("COMPOUNDOS_GIT_SHA", "UNKNOWN")
    timestamp = os.getenv("COMPOUNDOS_BUILD_TIMESTAMP", "UNKNOWN")
    version = os.getenv("COMPOUNDOS_APP_VERSION", "0.2.0")
    valid = bool(re.fullmatch("[0-9a-f]{40}", sha))
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        valid = valid and parsed.tzinfo is not None
    except ValueError:
        valid = False
    return {
        "git_sha": sha,
        "build_timestamp": timestamp,
        "application_version": version,
        "traceable": valid,
        "status": "TRACEABLE" if valid else "UNKNOWN",
    }
