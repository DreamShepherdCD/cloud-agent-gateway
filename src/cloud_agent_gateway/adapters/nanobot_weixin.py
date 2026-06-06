"""Adapter: nanobot.channels.weixin → cloud-agent-gateway's internal API.

This is the ONLY file in the framework that imports from nanobot's
weixin channel. When upstream changes WeixinChannel or WeixinConfig,
update the re-exports here — no other files need modification.
"""

from __future__ import annotations

from nanobot.channels.weixin import WeixinChannel, WeixinConfig

__all__ = ["WeixinChannel", "WeixinConfig"]
