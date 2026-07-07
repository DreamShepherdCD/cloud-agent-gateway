#!/usr/bin/env python3
"""
Zero-dependency setup reset via ``.reset-setup`` flag file.

When a space cannot boot into Phase 1 setup (e.g. leftover oauth.json
prevents it), drop a ``.reset-setup`` marker in the persistent volume
and restart.  The marker triggers unconditional oauth.json deletion.

Usage
─────
1. Upload ``.reset-setup`` to ``/data/`` or ``/mnt/workspace/`` via
   the platform web UI.
2. Restart the space.
3. ``platform_setup.py`` (or the CLI below) deletes oauth.json +
   the marker file.
4. The space restarts into Phase 1 setup.

Also callable directly:  ``python3 -m cloud_agent_gateway.reset_setup``

Safety
──────
- Only touches oauth.json — never config.json or any other file.
- Only triggers when the marker file exists (explicit user intent).
"""

from __future__ import annotations

import os
import sys

_PERSIST_ROOTS = ("/data", "/mnt/workspace")
_RESET_FLAG = ".reset-setup"
_OAUTH_FILE = "oauth.json"


def _find(path: str) -> str | None:
    """Return the first matching path across persistence roots."""
    for root in _PERSIST_ROOTS:
        full = os.path.join(root, path)
        if os.path.exists(full):
            return full
    return None


def _unlink(path: str) -> None:
    try:
        os.unlink(path)
        sys.stderr.write(f"[reset_setup] deleted: {path}\n")
    except FileNotFoundError:
        pass
    except Exception as exc:
        sys.stderr.write(f"[reset_setup] FAILED to delete {path}: {exc}\n")


def try_reset() -> str | None:
    """Check for .reset-setup flag and delete oauth.json if found.

    Returns a message string when reset was performed, None otherwise.
    """
    flag = _find(_RESET_FLAG)
    if flag is None:
        return None

    sys.stderr.write(f"[reset_setup] flag found: {flag}  →  cleaning up\n")

    oauth = _find(_OAUTH_FILE)
    if oauth:
        _unlink(oauth)
    _unlink(flag)

    return "oauth.json deleted — restart to enter Phase 1 setup"


# ── CLI ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    result = try_reset()
    if result:
        sys.stderr.write(f"[reset_setup] ✅ {result}\n")
    else:
        sys.stderr.write("[reset_setup] no .reset-setup flag found — nothing to do\n")
        sys.exit(1)
