"""binding_prompt.py — agent binding awareness injection

Provides prompt text and skill content that teaches the nanobot agent
how to guide users through WeChat/DingTalk channel binding.

Usage in Cloud Demo entrypoint:
    from cloud_agent_gateway.binding_prompt import BINDING_SKILL_MD
    # Write to ~/.nanobot/skills/channel-binding/SKILL.md
    # Or inject into config.system_prompt

The skill is self-contained — the agent only needs to know the API endpoints
and the conversation flow. Internal security is handled by the HTTP routes
(localhost-only check in oauth_proxy.py).
"""

# ═══════════════════════════════════════════════════════════════
# Skill definition (Markdown for nanobot skill system)
# ═══════════════════════════════════════════════════════════════

BINDING_SKILL_MD = """---
name: channel-binding
description: Guide user to bind WeChat/DingTalk/Discord/Telegram/MQTT channel from Space WebUI.
always: true
---

# Channel Binding

Bind WeChat (weixin) / DingTalk (dingtalk) channels for this agent.

## When to trigger

Check binding status on first interaction with each user, or when the user asks about WeChat/DingTalk.

## Check binding status

Send an internal HTTP GET:
```
GET http://127.0.0.1:7860/api/bind/status
```
Returns `{"wechat": {"bound": true/false}, "dingtalk": {"bound": true/false}}`.

## Bind WeChat

1. Tell user: "正在获取微信登录二维码..."
2. Call:
   ```
   POST http://127.0.0.1:7860/api/bind/wechat/qr
   ```
   Returns `{"qrcode_id": "...", "qrcode_img": "base64..."}`
3. Display the QR image to the user (decode base64 → PNG)
4. Tell user: "请用微信扫描二维码"
5. Poll every 2-3 seconds:
   ```
   GET http://127.0.0.1:7860/api/bind/wechat/status?qrcode=xxx
   ```
   Returns `{"status": "waiting|scanned|confirmed|expired", "message": "..."}`
6. On `"confirmed"`: tell user "微信绑定成功 ✅"
7. On `"expired"`: tell user "二维码已过期，重新获取..." → go to step 1

## Bind DingTalk

1. Ask user: "请提供钉钉 AppKey 和 AppSecret"
2. Tell user: "正在验证凭证..."
3. Call:
   ```
   POST http://127.0.0.1:7860/api/bind/dingtalk
   Content-Type: application/json
   {"client_id": "<AppKey>", "client_secret": "<AppSecret>"}
   ```
   Returns `{"ok": true, "message": "..."}` or `{"error": "..."}`
4. On success: tell user "钉钉绑定成功 ✅"
5. On failure: tell user the error and ask to retry

## First-interaction greeting

When a user first chats, check binding status silently. If any channel is unbound:

> 检测到你还未绑定微信/钉钉。回复「绑定微信」或「绑定钉钉」开始。

Only prompt once per user — don't nag after they decline or complete binding.

## Security

- All bind endpoints are localhost-only (no external access)
- WeChat QR data flows directly: ilink API → agent → user
- DingTalk credentials are validated before saving
- No third-party data transmission
"""

# ═══════════════════════════════════════════════════════════════
# Minimal system prompt injection (optional, for agents without
# skill loading)
# ═══════════════════════════════════════════════════════════════

BINDING_SYSTEM_PROMPT = (
    "You can help users bind WeChat and DingTalk channels.\n\n"
    "To check binding status, silently call GET http://127.0.0.1:7860/api/bind/status "
    "on the first interaction with each user.\n"
    "If wechat or dingtalk is unbound, proactively offer help:\n"
    '  "检测到你还未绑定微信/钉钉。回复「绑定微信」或「绑定钉钉」开始。"\n\n'
    "WeChat flow: POST /api/bind/wechat/qr → display QR → poll /api/bind/wechat/status?qrcode=xxx\n"
    "DingTalk flow: ask AppKey+AppSecret → POST /api/bind/dingtalk → confirm\n\n"
    "All endpoints are at http://127.0.0.1:7860 (internal, no auth needed)."
)


def inject_binding_skill(skills_dir: str) -> str:
    """Write the channel-binding skill to a skills directory.

    Returns the path to the created SKILL.md.
    """
    import os
    skill_dir = os.path.join(skills_dir, "channel-binding")
    os.makedirs(skill_dir, exist_ok=True)
    skill_path = os.path.join(skill_dir, "SKILL.md")
    with open(skill_path, "w", encoding="utf-8") as f:
        f.write(BINDING_SKILL_MD)
    return skill_path
