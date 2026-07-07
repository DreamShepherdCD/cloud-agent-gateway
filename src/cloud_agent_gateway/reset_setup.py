#!/usr/bin/env python3
"""
Zero-dependency setup reset — breaks deadlock when a space has stale
oauth.json but no config.json (cannot enter Phase 2, stuck restarting).

Three trigger paths
───────────────────
1. **Auto-cleanup** — ``platform_setup.py`` calls ``try_auto_reset()`` at
   module level *before* any third-party imports.  If oauth.json exists but
   no config.json is found under instances/, oauth.json is deleted so the
   space restarts into Phase 1 setup.

2. **Flag file** — Drop a ``.reset-setup`` file in the persistent volume
   (``/data/`` or ``/mnt/workspace/``) via the platform web UI, then
   restart.  Unconditional oauth.json cleanup.

3. **CLI** — ``python3 -m cloud_agent_gateway.reset_setup`` (available as
   long as the container is running enough to exec a command).

Safety
──────
- Never touches config.json.
- Auto-cleanup requires oauth.json *AND* zero config.json files (both
  conditions must be true).  A healthy space has both → skipped.
"""

from __future__ import annotations

import os
import sys

# ── Persistence roots (HF / ModelScope) ──────────────────────────
_PERSIST_ROOTS = ("/data", "/mnt/workspace")
_RESET_FLAG = ".reset-setup"
_OAUTH_FILE = "oauth.json"

_sys_stderr = sys.stderr
_sys_stderr.write("[reset_setup] DEBUG module loaded\n")


def _find_root(name: str) -> list[str]:
    """Return paths to *name* across all persistence roots."""
    found = []
    for root in _PERSIST_ROOTS:
        path = os.path.join(root, name)
        if os.path.exists(path):
            found.append(path)
    return found


def _any_config_json() -> bool:
    """True if any config.json exists under instances/ in any root."""
    for root in _PERSIST_ROOTS:
        instances_dir = os.path.join(root, "instances")
        if not os.path.isdir(instances_dir):
            continue
        try:
            for agent in os.listdir(instances_dir):
                if os.path.exists(os.path.join(instances_dir, agent, "config.json")):
                    return True
        except PermissionError:
            pass
    return False


def _log(msg: str) -> None:
    sys.stderr.write(f"[reset_setup] {msg}\n")


# ── Public API ───────────────────────────────────────────────────


def try_auto_reset() -> str | None:
    """Run auto-cleanup check.  Returns a message if reset was performed.

    Called by platform_setup.py at module level.  Two conditions trigger
    deletion of oauth.json:

    1. ``.reset-setup`` flag file exists (manual trigger).
    2. oauth.json exists but no config.json anywhere (incomplete install).

    Never touches config.json — only oauth.json is deleted.
    """
    _log("DEBUG scanning...")
    flag_paths = _find_root(_RESET_FLAG)
    oauth_paths = _find_root(_OAUTH_FILE)
    has_config = _any_config_json()
    _log(f"DEBUG flags={flag_paths} oauth={oauth_paths} has_config={has_config}")

    # ── Manual reset via flag file ──
    if flag_paths:
        for fp in flag_paths:
            _log(f"flag found: {fp}  →  forcing cleanup")
        for op in oauth_paths:
            _unlink(op)
        for fp in flag_paths:
            _unlink(fp)
        return "reset_setup: manual reset via .reset-setup flag"

    # ── Auto-cleanup: oauth but no config → incomplete install ──
    if oauth_paths and not has_config:
        _log("DEBUG entering auto-cleanup (oauth exists, no config)")
        for op in oauth_paths:
            _unlink(op)
        return "reset_setup: auto-cleanup — oauth.json present but no config.json"

    _log(f"DEBUG skipping (oauth={'yes' if oauth_paths else 'no'} config={'yes' if has_config else 'no'})")
    return None


def _unlink(path: str) -> None:
    try:
        os.unlink(path)
        _log(f"deleted: {path}")
    except FileNotFoundError:
        pass
    except Exception as exc:
        _log(f"FAILED to delete {path}: {exc}")


# ── CLI ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    result = try_auto_reset()
    if result:
        _log(f"✅ {result}")
    else:
        _log("nothing to do — either no oauth.json or config.json exists")
