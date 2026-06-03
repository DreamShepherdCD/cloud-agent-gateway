"""
HF Direct / Local Fallback Platform.

Used when no cloud platform is detected (HF_Direct on HuggingFace,
local Docker deployment, or any non-cloud environment).

No OAuth — uses native nanobot authentication.
Squad Legion extensions return safe defaults.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware

from cloud_agent_gateway.platforms.base import CloudPlatformProtocol


class HFDirectPlatform(CloudPlatformProtocol):
    """Fallback platform for local / HF Direct deployments."""

    name = "hf-direct"

    # ── Filesystem ──

    @property
    def data_root(self) -> str:
        return "/data"

    def instance_path(self, name: str) -> str:
        return f"{self.data_root}/instances/{name}"

    # ── OAuth (not supported on local/direct) ──

    def register_oauth(self) -> Any:
        return None

    login_route_path = "/login"
    callback_route_path = "/auth/callback"

    async def exchange_token(self, request: Any) -> dict | None:
        return None

    async def fetch_userinfo(self, token: dict) -> dict | None:
        return None

    def extract_username(self, userinfo: dict) -> str:
        return userinfo.get("name", "Unknown") if userinfo else "Unknown"

    # ── Squad Legion: Auth & Session ──

    @property
    def public_paths(self) -> list[str]:
        return ["/health"]

    def create_auth_middleware(self) -> BaseHTTPMiddleware | None:
        return None

    def register_routes(self, app: FastAPI) -> None:
        pass

    async def startup(self) -> None:
        pass

    @property
    def session_kwargs(self) -> dict:
        return {"secret_key": "hf-direct-fallback", "max_age": 86400}

    # ── Squad Legion: User Management ──

    def get_commander_whitelist(self) -> list[str]:
        return ["*"] if os.environ.get("COMMANDER_WHITELIST", "*") == "*" else [os.environ.get("COMMANDER_WHITELIST", "")]

    def get_user_agent_map(self) -> dict[str, str]:
        return {}

    def get_agent_for_user(self, username: str) -> str:
        return "neo"

    def is_commander(self, session_user: Any) -> bool:
        return True

    def check_relay_permission(self, sender: str, target: str) -> bool:
        return True

    def is_member(self, username: str) -> bool:
        return True

    # ── Squad Legion: Commander & Config ──

    def process_commander_message(
        self, data: str, username: str, real_name: str, is_commander: bool
    ) -> tuple[str | None, str | None]:
        return (data, None)

    def refresh_config(self, agent_name: str, config_dir: str) -> bool:
        return False

    # ── Entrypoint setup ──

    @staticmethod
    def setup() -> str:
        return ""

    # ── Header stripping ───────────────────────────────────────

    @property
    def stripped_inbound_headers(self) -> list[str]:
        """No cloud proxy — all headers pass through."""
        return []
