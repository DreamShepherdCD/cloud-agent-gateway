"""
ModelScope Studio Cloud Platform — Cloud Demo (single-agent, nanobot engine).

Handles ModelScope OAuth, filesystem paths, and platform-specific
initialisation.  Uses manual httpx OAuth flow to bypass authlib
nonce-validation failures on ModelScope.

For Squad (multi-agent) ModelScope support, see ``modelscope_squad.py``.
"""

from __future__ import annotations

import json as _json
import logging
import os
import re
import subprocess
import sys
from typing import Any

import httpx
from authlib.integrations.starlette_client import OAuth

from cloud_agent_gateway.platforms.base import CloudPlatformProtocol
from cloud_agent_gateway.platforms._credentials import read_oauth_json

logger = logging.getLogger("cloud.modelscope")

_MODELSCOPE_OIDC_CONFIG = "https://modelscope.cn/.well-known/openid-configuration"


def _log(msg: str) -> None:
    sys.stderr.write(f"[modelscope] {msg}\n")
    sys.stderr.flush()


def _get_oauth_client() -> OAuth:
    """Create a minimal OAuth object for ModelScope.

    Registers the MS provider by hand because authlib's automatic OIDC
    discovery causes nonce-validation failures on ModelScope.
    """
    oauth = OAuth()
    client_id, client_secret = read_oauth_json()
    oauth.register(
        name="modelscope",
        client_id=client_id,
        client_secret=client_secret,
        server_metadata_url=_MODELSCOPE_OIDC_CONFIG,
        client_kwargs={
            "scope": "profile",  # avoid 'openid' → no nonce
            "token_endpoint_auth_method": "client_secret_post",
        },
    )
    return oauth


class ModelScopeDatasetSyncMixin:
    """Mixin: mirror persistent storage to a ModelScope dataset via git.

    Subclasses must set class attributes:
      - ``_dataset_repo``: ``"owner/repo-name"`` on ModelScope
      - ``_dataset_token_env``: env var name holding the MS access token

    Optional overrides:
      - ``_mirror_path``: local clone path (default ``/mnt/workspace/dataset-mirror``)
      - ``_source_path``: directory to mirror (default ``/mnt/workspace/instances``)
    """

    _dataset_repo: str = ""
    _dataset_token_env: str = "NANOBOT_Staging_modelscope_TOKEN"
    _mirror_path: str = "/mnt/workspace/dataset-mirror"
    _source_path: str = "/mnt/workspace/instances"

    _sync_ready: bool = False
    _sync_lock = None
    _sync_dirty: bool = False
    _sync_thread = None

    # Dataset pull timer (dataset → container)
    _pull_interval: int = 60  # seconds between checks
    _pull_timer_started: bool = False
    _git_op_lock = None  # serialise git working-tree ops

    # ──────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────

    def _get_ms_token(self) -> str:
        """Read the ModelScope access token from env or /proc/1/environ."""
        token = os.environ.get(self._dataset_token_env, "")
        if not token:
            try:
                with open("/proc/1/environ", "rb") as f:
                    for item in f.read().split(b"\0"):
                        needle = self._dataset_token_env.encode()
                        if needle in item:
                            token = item.decode("utf-8", errors="replace").split("=", 1)[1]
                            break
            except Exception:
                pass
        return token

    # ──────────────────────────────────────────────────────
    # Persistent storage sync (read -> mirror -> git push)
    # ──────────────────────────────────────────────────────

    def _ensure_sync_ready(self) -> None:
        """Lazily clone dataset mirror to ``_mirror_path``."""
        if self._sync_ready:
            return
        import subprocess as _sp
        ms_token = self._get_ms_token()
        mirror = self._mirror_path
        import shutil as _sh
        need_clone = True
        if os.path.isdir(f"{mirror}/.git"):
            r = _sp.run(["git", "remote", "get-url", "origin"], cwd=mirror,
                       capture_output=True, timeout=5)
            if r.returncode != 0:
                logger.warning("_ensure_sync_ready: broken mirror (no remote), re-cloning")
                _sh.rmtree(mirror, ignore_errors=True)
            else:
                need_clone = False
                try:
                    _sp.run(["git", "fetch", "origin", "master"], cwd=mirror,
                            capture_output=True, timeout=30)
                    _sp.run(["git", "reset", "--hard", "origin/master"], cwd=mirror,
                            capture_output=True, timeout=10)
                    logger.info("_ensure_sync_ready: pulled latest from dataset")
                except Exception as exc:
                    logger.warning("_ensure_sync_ready: pull failed: %s", exc)
        if need_clone:
            if not ms_token:
                logger.warning("_ensure_sync_ready: no MS token, dataset sync disabled")
                return
            clone_url = f"https://oauth2:{ms_token}@www.modelscope.cn/datasets/{self._dataset_repo}.git"
            _sh.rmtree(mirror, ignore_errors=True)
            try:
                _sp.run(["git", "clone", "--depth=1", clone_url, mirror],
                        check=True, capture_output=True, timeout=60)
                logger.info("_ensure_sync_ready: cloned dataset mirror")
            except Exception as exc:
                logger.warning("_ensure_sync_ready: clone failed: %s", exc)
                return
        self._sync_ready = True
        if not self._pull_timer_started:
            self._start_dataset_pull_timer()

    # ──────────────────────────────────────────────────────
    # Dataset pull timer (dataset → container)
    # ──────────────────────────────────────────────────────

    def _start_dataset_pull_timer(self) -> None:
        """Start a daemon thread that periodically polls the dataset for updates.

        When new commits are detected the mirror is fast-forwarded and
        :meth:`_merge_dataset_configs_to_instances` applies config changes to
        the live instances.
        """
        import threading as _th
        import time as _time

        self._pull_timer_started = True

        def _loop():
            _time.sleep(self._pull_interval)
            while True:
                try:
                    self._check_and_apply_dataset_updates()
                except Exception as exc:
                    logger.warning("dataset pull timer: %s", exc)
                _time.sleep(self._pull_interval)

        t = _th.Thread(target=_loop, daemon=True, name="dataset-pull-timer")
        t.start()
        logger.info("dataset pull timer started (interval=%ss)", self._pull_interval)

    def _check_and_apply_dataset_updates(self) -> None:
        """Fetch origin/master; if it advanced, pull and merge configs."""
        if not self._sync_ready:
            return

        import subprocess as _sp
        mirror = self._mirror_path

        # Current HEAD
        r = _sp.run(["git", "rev-parse", "HEAD"], cwd=mirror,
                    capture_output=True, timeout=5)
        if r.returncode != 0:
            return
        old_head = r.stdout.decode().strip()

        # Fetch remote
        r = _sp.run(["git", "fetch", "origin", "master"], cwd=mirror,
                    capture_output=True, timeout=30)
        if r.returncode != 0:
            logger.warning("dataset pull timer: fetch failed")
            return

        # Compare
        r = _sp.run(["git", "rev-parse", "origin/master"], cwd=mirror,
                    capture_output=True, timeout=5)
        new_head = r.stdout.decode().strip()

        if old_head == new_head:
            return  # nothing new

        logger.info("dataset pull timer: new commits (%s → %s), pulling…",
                    old_head[:8], new_head[:8])

        # Serialise with _do_sync
        import threading as _th
        if self._git_op_lock is None:
            self._git_op_lock = _th.Lock()
        with self._git_op_lock:
            # Apply incoming changes to mirror working tree
            r = _sp.run(["git", "merge", "origin/master", "--no-edit"],
                        cwd=mirror, capture_output=True, timeout=10)
            if r.returncode != 0:
                logger.warning("dataset pull timer: merge failed: %s",
                               r.stderr.decode(errors="replace")[-200:])
                # Attempt to reset to clean state
                _sp.run(["git", "merge", "--abort"], cwd=mirror,
                        capture_output=True, timeout=5)
                return

        # Merge config.json files into live instances
        self._merge_dataset_configs_to_instances()

    def _merge_dataset_configs_to_instances(self) -> None:
        """Deep-merge config.json from dataset mirror → live instances.

        Dataset values are authoritative for scalars; nested dicts (channels)
        are merged recursively so per-agent credentials survive.
        """
        import json as _json

        mirror = self._mirror_path
        instances_dst = self._source_path
        mirror_instances = f"{mirror}/instances"

        if not os.path.isdir(mirror_instances):
            return

        def _deep_merge(base: dict, override: dict) -> dict:
            for key, value in override.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                    _deep_merge(base[key], value)
                else:
                    base[key] = value
            return base

        for item in os.listdir(mirror_instances):
            if item in ("_template", ".git"):
                continue
            ds_cfg_path = f"{mirror_instances}/{item}/config.json"
            if not os.path.isfile(ds_cfg_path):
                continue

            dst_cfg = f"{instances_dst}/{item}/config.json"
            if not os.path.isfile(dst_cfg):
                continue

            try:
                with open(ds_cfg_path) as f:
                    ds_cfg = _json.load(f)
                with open(dst_cfg) as f:
                    inst_cfg = _json.load(f)

                merged = _deep_merge(inst_cfg, ds_cfg)
                if merged != inst_cfg:
                    with open(dst_cfg, "w") as f:
                        _json.dump(merged, f, indent=2, ensure_ascii=False)
                    logger.info("dataset pull timer: merged config.json for %s", item)
            except Exception as exc:
                logger.warning("dataset pull timer: failed to merge %s: %s", item, exc)

    # ──────────────────────────────────────────────────────
    # Persistent storage sync (container → dataset)
    # ──────────────────────────────────────────────────────

    def _on_persistent_write(self) -> None:
        """Schedule a background sync to the dataset mirror.

        Multiple rapid writes collapse into a single sync via debounce.
        """
        import threading as _th
        if self._sync_lock is None:
            self._sync_lock = _th.Lock()
        with self._sync_lock:
            if self._sync_thread and self._sync_thread.is_alive():
                self._sync_dirty = True
                return
            self._sync_dirty = False
        self._sync_thread = _th.Thread(target=self._do_sync, daemon=True)
        self._sync_thread.start()

    def _do_sync(self) -> None:
        """Mirror ``_source_path`` into dataset clone and push."""
        import shutil as _sh
        import subprocess as _sp
        import time as _time
        import threading as _th

        _time.sleep(1)
        self._ensure_sync_ready()
        if not self._sync_ready:
            return

        mirror = self._mirror_path
        src = self._source_path
        dst = f"{mirror}/instances"

        # Serialise with pull timer (lock covers all git working-tree ops)
        if self._git_op_lock is None:
            self._git_op_lock = _th.Lock()

        with self._git_op_lock:
            try:
                # Pull latest from dataset so push won't be rejected
                _sp.run(["git", "fetch", "origin", "master"], cwd=mirror,
                        capture_output=True, timeout=30)
                _sp.run(["git", "reset", "--hard", "origin/master"], cwd=mirror,
                        capture_output=True, timeout=10)

                if os.path.isdir(dst):
                    if os.path.isdir(f"{dst}/workspace"):
                        _sh.rmtree(dst)
                    else:
                        for sub in os.listdir(dst):
                            sub_p = os.path.join(dst, sub)
                            if os.path.isdir(sub_p):
                                _sh.rmtree(sub_p)
                            else:
                                os.unlink(sub_p)
                _sh.copytree(src, dst, dirs_exist_ok=True)
                _sh.rmtree(f"{dst}/.git", ignore_errors=True)  # instances is a git repo → would become submodule
                if os.path.isfile(f"{dst}/.gitignore"):
                    os.unlink(f"{dst}/.gitignore")  # nanobot git store gitignore blocks sync

                _sp.run(["git", "add", "-A"], cwd=mirror,
                        capture_output=True, timeout=10)
                r = _sp.run(["git", "diff", "--cached", "--quiet"], cwd=mirror, timeout=5)
                if r.returncode == 0:
                    logger.debug("_do_sync: no changes to push")
                    return

                result = _sp.run(
                    ["git", "commit", "-m", "sync: instances -> dataset mirror"],
                    cwd=mirror, capture_output=True, timeout=10)
                if result.returncode != 0:
                    logger.warning("_do_sync: git commit failed: %s",
                                   result.stderr.decode(errors="replace")[-300:])
                    return

                result = _sp.run(
                    ["git", "push", "origin", "HEAD:master"],
                    cwd=mirror, capture_output=True, timeout=30)
                if result.returncode != 0:
                    logger.warning("_do_sync: git push failed: %s",
                                   result.stderr.decode(errors="replace")[-300:])
                    return
                logger.info("_do_sync: pushed to dataset mirror")

                if self._sync_lock:
                    with self._sync_lock:
                        if self._sync_dirty:
                            self._sync_dirty = False
                            self._sync_thread = _th.Thread(target=self._do_sync, daemon=True)
                            self._sync_thread.start()
            except Exception as exc:
                logger.warning("_do_sync: sync failed: %s", exc)


class ModelScopePlatform(ModelScopeDatasetSyncMixin, CloudPlatformProtocol):
    """Platform implementation for ModelScope Studio Cloud Demo."""

    name = "modelscope"
    _dataset_repo = "DreamShepherd/ms-nanobot-cloud-demo-data"
    _dataset_token_env = "ms_nanobot_cloud_demo"

    # ── Filesystem ──

    @property
    def data_root(self) -> str:
        return "/mnt/workspace"

    def instance_path(self, name: str) -> str:
        return f"{self.data_root}/instances/{name}"

    # Cloud Demo sessions live at data-root level (upstream nanobot layout),
    # not under a specific instance's workspace/.
    def _session_path(self, agent_id: str, session_key: str) -> str:
        return f"{self.data_root}/instances/sessions/websocket_{session_key}.jsonl"

    # ── OAuth ──

    def register_oauth(self) -> Any:
        return _get_oauth_client()

    login_route_path = "/login"
    # Cloud Demo uses OAuth proxy on /api/auth/*; staging uses nanobot directly on /auth/*
    callback_route_path = os.environ.get("OAUTH_CALLBACK_PATH", "/api/auth/callback")

    async def exchange_token(self, request: Any) -> dict | None:
        """Manual OAuth token exchange — bypasses authlib nonce issues on MS."""
        code = request.query_params.get("code")
        if not code:
            return None

        client_id, client_secret = read_oauth_json()
        redirect_uri = str(request.url).split("?")[0]

        async with httpx.AsyncClient(timeout=15) as http:
            token_resp = await http.post(
                f"{_MODELSCOPE_OIDC_CONFIG.replace('.well-known/openid-configuration', '')}oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                },
                headers={"Accept": "application/json"},
            )
            if token_resp.status_code != 200:
                logger.warning(f"Token exchange failed: {token_resp.text[:200]}")
                return None

            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            if not access_token:
                return None

            user_resp = await http.get(
                f"{_MODELSCOPE_OIDC_CONFIG.replace('.well-known/openid-configuration', '')}oauth/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if user_resp.status_code != 200:
                return None

            userinfo = user_resp.json()
            _log(f"userinfo: {_json.dumps(userinfo)}")
            return {"userinfo": userinfo, "access_token": access_token}



    def extract_username(self, userinfo: dict) -> str:
        return (
            userinfo.get("preferred_username")
            or userinfo.get("username")
            or userinfo.get("nickname")
            or userinfo.get("name")
            or userinfo.get("user_nickname")
            or userinfo.get("nick_name")
            or userinfo.get("login")
            or userinfo.get("sub", "")
        )

    # ── Entrypoint setup ──

    @staticmethod
    def setup() -> str:
        """MS Cloud Demo initialisation: unfreeze env, auto-detect owner."""
        return ModelScopePlatform._setup_cloud_demo()

    @staticmethod
    def _setup_cloud_demo() -> str:
        """Cloud Demo setup: unfreeze env, auto-detect SPACE_AUTHOR from git."""
        exports: list[str] = []
        proc_env = "/proc/1/environ"

        # ── Auto-detect owner from git remote URL ──
        owner = ""
        try:
            result = subprocess.run(
                ["git", "config", "--get", "remote.origin.url"],
                capture_output=True, text=True, cwd="/app", timeout=5,
            )
            url = result.stdout.strip()
            m = re.search(r'/studios/([^/]+)/', url)
            if m:
                owner = m.group(1)
            _log(f"git remote: {url!r} → owner={owner!r}")
        except Exception as exc:
            _log(f"git parse warning: {exc}")

        if owner:
            os.environ["SPACE_AUTHOR"] = owner
            exports.append(f"export SPACE_AUTHOR='{owner}'")

        # ── Unfreeze env vars from /proc/1/environ ──
        if os.path.exists(proc_env):
            try:
                with open(proc_env, "rb") as f:
                    raw = f.read().split(b"\0")
                for item in raw:
                    if not item:
                        continue
                    try:
                        name, value = item.decode("utf-8", errors="replace").split("=", 1)
                    except ValueError:
                        continue
                    if name.startswith(("NANOBOT_", "OAUTH_", "DEEPSEEK_")):
                        exports.append(f"export {name}='{value}'")
                        os.environ[name] = value
            except Exception as exc:
                _log(f"env unfreeze failed: {exc}")

        # Ensure correct data root for ModelScope
        exports.append("export DATA_ROOT='/mnt/workspace'")
        return "\n".join(exports)

    # ── Header stripping ───────────────────────────────────────

    @property
    def proxy_header_blacklist(self) -> list[str]:
        """ModelScope injects x-ms-* headers that must be stripped before
        proxying to internal agents."""
        return super().proxy_header_blacklist + [
            "x-ms-client-request-id",
            "x-ms-client-principal",
            "x-ms-client-principal-name",
        ]

    @property
    def stripped_inbound_headers(self) -> list[str]:
        """ModelScope Studio proxy strips Authorization and Set-Cookie.

        This is why we use token-in-URL flow for WebSocket auth and manual
        httpx OAuth (bypassing session-cookie-based CSRF).
        """
        return ["authorization", "set-cookie"]

    # ── Session Middleware ──

    @property
    def session_kwargs(self) -> dict:
        return {
            "secret_key": os.environ.get(
                "SESSION_SECRET", "nanobot_modelscope_secret_k8s"
            ),
            "https_only": True,
            "same_site": "none",
        }



