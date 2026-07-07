#!/usr/bin/env python3
"""
Zero-dependency setup reset via ``reset-setup`` flag file.

When a space cannot boot into Phase 1 setup (e.g. leftover oauth.json
prevents it), edit ``reset-setup`` to ``PURGE_OAUTH=1`` and rebuild.
The marker triggers unconditional oauth.json deletion.

Usage
─────
1. Edit ``reset-setup`` alongside Dockerfile: set ``PURGE_OAUTH=1``.
2. Push + rebuild (or Factory Rebuild).
3. ``platform_setup.py`` deletes oauth.json + sets ``PURGE_OAUTH=0``.
4. The space restarts into Phase 1 setup.
5. Edit ``reset-setup`` back to ``PURGE_OAUTH=0`` in the repo so future
   rebuilds don't re-trigger.

Also callable directly:  ``python3 -m cloud_agent_gateway.reset_setup``

Safety
──────
- Only triggers when marker contains ``PURGE_OAUTH=1``.
- Only touches oauth.json — never config.json or any other file.
"""

from __future__ import annotations

import os
import sys

# Where oauth.json lives (persistent volume)
_OAUTH_ROOTS = ("/data", "/mnt/workspace")
# Where the flag file lives (copied from repo by Dockerfile)
_FLAG_ROOTS = ("/app", os.getcwd())
_FLAG_FILE = "reset-setup"
_OAUTH_FILE = "oauth.json"

# ── helpers ──────────────────────────────────────────────────────


def _find(path: str | None, roots: tuple[str, ...]) -> str | None:
    for root in roots:
        if path is None:
            full = root
        else:
            full = os.path.join(root, path)
        if os.path.exists(full):
            return full
    return None


def _read(path: str) -> str:
    try:
        with open(path) as f:
            return f.read().strip()
    except Exception:
        return ""


def _unlink(path: str) -> None:
    try:
        os.unlink(path)
        sys.stderr.write(f"[reset_setup] deleted: {path}\n")
    except FileNotFoundError:
        pass
    except Exception as exc:
        sys.stderr.write(f"[reset_setup] FAILED to delete {path}: {exc}\n")


# ── main logic ───────────────────────────────────────────────────


def try_reset() -> str | None:
    """Check reset-setup flag.  Trigger when file contains ``PURGE_OAUTH=1``.

    Returns a message string when reset was performed, None otherwise.
    """
    flag = _find(_FLAG_FILE, _FLAG_ROOTS)
    if flag is None:
        return None

    content = _read(flag)
    if "PURGE_OAUTH=1" not in content:
        return None  # present but not armed

    sys.stderr.write(f"[reset_setup] flag armed: {flag}  →  cleaning up\n")

    oauth = _find(_OAUTH_FILE, _OAUTH_ROOTS)
    if oauth:
        _unlink(oauth)

    # Reset flag so this rebuild's copy won't re-trigger,
    # but repo still has the file for next COPY on future rebuilds.
    try:
        with open(flag, "w") as f:
            f.write("PURGE_OAUTH=0\n")
    except Exception:
        pass

    return "oauth.json deleted — restart to enter Phase 1 setup"


# ── CLI ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    result = try_reset()
    if result:
        sys.stderr.write(f"[reset_setup] ✅ {result}\n")
    else:
        sys.stderr.write("[reset_setup] not armed — nothing to do\n")
        sys.exit(1)
