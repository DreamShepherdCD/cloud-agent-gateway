"""
Read pip ``direct_url.json`` for git-installed packages and build GitHub
markdown links with version/commit info.  Used by the system-config chat
in both single-agent (oauth_proxy) and multi-agent (gatekeeper) modes.
"""

from __future__ import annotations

import json
import os


def get_package_source(pkg_name: str) -> dict | None:
    """Read pip direct_url.json → {repo, revision, commit, url} or None."""
    try:
        from importlib.metadata import distribution
        dist = distribution(pkg_name)
    except Exception:
        return None
    direct_url = dist._path / "direct_url.json"
    if not direct_url.is_file():
        return None
    try:
        info = json.loads(direct_url.read_text())
    except Exception:
        return None
    url = info.get("url", "")
    repo = ""
    if "github.com/" in url:
        repo = url.split("github.com/")[-1].replace(".git", "")
    revision = ""
    commit = ""
    vcs = info.get("vcs_info", {})
    if isinstance(vcs, dict):
        revision = vcs.get("requested_revision", "")
        commit = vcs.get("commit_id", "")
    return {"repo": repo, "revision": revision, "commit": commit, "url": url}


def build_source_link(
    info: dict | None, default_repo: str, default_branch: str = ""
) -> str:
    """Build a GitHub markdown link from package source info, with fallback."""
    if info and info.get("repo"):
        repo = info["repo"]
        rev = info.get("revision", "")
        commit_short = info.get("commit", "")[:7] if info.get("commit") else ""

        if rev.startswith("v"):
            display = f"{repo} @{rev}"
            href = f"https://github.com/{repo}/tree/{rev}"
        elif rev and len(rev) >= 7:
            display = f"{repo} @{rev[:7]}"
            href = f"https://github.com/{repo}/commit/{commit_short or rev[:7]}"
        elif commit_short:
            display = f"{repo} @{commit_short}"
            href = f"https://github.com/{repo}/commit/{commit_short}"
        else:
            display = repo
            href = f"https://github.com/{repo}"
    else:
        repo = default_repo
        display = repo
        if default_branch:
            href = f"https://github.com/{repo}/tree/{default_branch}"
        else:
            href = f"https://github.com/{repo}"

    return f"[{display}]({href})"
