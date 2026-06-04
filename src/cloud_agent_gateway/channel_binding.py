"""cloud_agent_gateway — 频道绑定（微信扫码 / 钉钉凭证）

用于 Cloud Demo 空间：原生 nanobot agent 通过 internal HTTP 调用绑定 API。
安全模型：仅允许 localhost 内部调用，agent 传入 sender_id 标识用户。

源码依赖：
  nanobot.channels.weixin — ilink API 常量、WeixinChannel（与官方同一接口）
"""

import json
import os

import httpx
from nanobot.channels.weixin import (
    ILINK_APP_ID,
    ILINK_APP_CLIENT_VERSION,
    WEIXIN_CHANNEL_VERSION,
    WeixinChannel,
)

_RANDOM_UIN = WeixinChannel._random_wechat_uin
ILINK_BASE_URL = "https://ilinkai.weixin.qq.com"

# ── In-memory QR sessions ──
_pending: dict[str, dict] = {}


# ══════════════════════════════════════════════════
# ilink helpers (mirrors WeixinChannel._make_headers / _api_get)
# ══════════════════════════════════════════════════

def _ilink_headers(auth_token: str = "") -> dict:
    headers = {
        "X-WECHAT-UIN": _RANDOM_UIN(),
        "Content-Type": "application/json",
        "AuthorizationType": "ilink_bot_token",
        "iLink-App-Id": ILINK_APP_ID,
        "iLink-App-ClientVersion": str(ILINK_APP_CLIENT_VERSION),
    }
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    return headers


async def _ilink_get(endpoint: str, params: dict | None = None) -> dict:
    url = f"{ILINK_BASE_URL}/{endpoint}"
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
        resp = await c.get(url, params=params, headers=_ilink_headers())
        resp.raise_for_status()
        return resp.json()


async def _ilink_get_with_base(base_url: str, endpoint: str, params: dict | None = None) -> dict:
    url = f"{base_url.rstrip('/')}/{endpoint}"
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
        resp = await c.get(url, params=params, headers=_ilink_headers())
        resp.raise_for_status()
        return resp.json()


# ══════════════════════════════════════════════════
# State paths
# ══════════════════════════════════════════════════

def _nanobot_home() -> str:
    """nanobot 主目录（容器内 ~/.nanobot）"""
    return os.path.expanduser("~/.nanobot")


def _weixin_state_dir() -> str:
    d = os.path.join(_nanobot_home(), "weixin")
    os.makedirs(d, exist_ok=True)
    return d


def _config_path() -> str:
    return os.path.join(_nanobot_home(), "config.json")


def _load_json(path: str) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


# ══════════════════════════════════════════════════
# WeChat QR login (mirrors WeixinChannel._fetch_qr_code + _qr_login)
# ══════════════════════════════════════════════════

async def wechat_fetch_qr() -> dict:
    """获取微信登录二维码。返回 {qrcode_id, qrcode_img}。"""
    try:
        data = await _ilink_get("ilink/bot/get_bot_qrcode", params={"bot_type": "3"})
    except Exception as e:
        return {"error": f"获取微信二维码失败: {e}"}

    qid = data.get("qrcode", "")
    img = data.get("qrcode_img_content", "")
    if not qid:
        return {"error": "微信 API 未返回二维码"}

    _pending[qid] = {"status": "waiting", "sender_id": "", "token": ""}
    return {"qrcode_id": qid, "qrcode_img": img}


async def wechat_check_status(qrcode_id: str) -> dict:
    """轮询微信扫码状态。"""
    bind = _pending.get(qrcode_id)
    if not bind:
        return {"status": "expired", "message": "二维码已过期"}

    try:
        data = await _ilink_get_with_base(
            base_url=bind.get("base_url", ILINK_BASE_URL),
            endpoint="ilink/bot/get_qrcode_status",
            params={"qrcode": qrcode_id},
        )
    except Exception as e:
        return {"status": "error", "message": str(e)}

    if not isinstance(data, dict):
        return {"status": "waiting", "message": "等待扫码..."}

    status = data.get("status", "wait")

    if status == "confirmed":
        token = data.get("bot_token", "")
        base_url = data.get("baseurl", "")
        if not token:
            return {"status": "error", "message": "未返回 token"}

        bind["status"] = "confirmed"
        bind["token"] = token

        # 写入 account.json（与 WeixinChannel._save_state 兼容）
        acc = os.path.join(_weixin_state_dir(), "account.json")
        existing = _load_json(acc)
        existing["token"] = token
        if base_url:
            existing["base_url"] = base_url
        with open(acc, "w") as f:
            json.dump(existing, f, ensure_ascii=False)

        return {"status": "confirmed", "message": "微信已绑定"}

    elif status in ("scaned", "scaned_but_redirect"):
        if status == "scaned_but_redirect":
            rh = str(data.get("redirect_host", "") or "").strip()
            if rh:
                if not (rh.startswith("http://") or rh.startswith("https://")):
                    rh = f"https://{rh}"
                bind["base_url"] = rh
        return {"status": "scanned", "message": "已扫码，等待确认..."}

    elif status == "expired":
        del _pending[qrcode_id]
        return {"status": "expired", "message": "二维码已过期"}

    return {"status": "waiting", "message": "等待扫码..."}


# ══════════════════════════════════════════════════
# DingTalk credential binding
# ══════════════════════════════════════════════════

async def dingtalk_bind(client_id: str, client_secret: str) -> dict:
    """验证并写入钉钉凭证。"""
    if not client_id or not client_secret:
        return {"error": "client_id 和 client_secret 不能为空"}

    # 验证凭证可用性
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.post(
                "https://api.dingtalk.com/v1.0/oauth2/accessToken",
                json={"appKey": client_id, "appSecret": client_secret},
            )
            if resp.status_code != 200:
                return {"error": f"钉钉凭证无效 ({resp.status_code})"}
    except Exception as e:
        return {"error": f"无法连接钉钉 API: {e}"}

    # 写入 config.json（与 nanobot dingtalk channel 配置兼容）
    cp = _config_path()
    cfg = _load_json(cp)
    if "channels" not in cfg:
        cfg["channels"] = {}
    cfg["channels"]["dingtalk"] = {
        "enabled": True,
        "clientId": client_id,
        "clientSecret": client_secret,
        "allowFrom": ["*"],
    }
    with open(cp, "w") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

    return {"ok": True, "message": "钉钉已绑定"}


# ══════════════════════════════════════════════════
# Binding status query
# ══════════════════════════════════════════════════

def bind_status() -> dict:
    """查询当前绑定状态。"""
    wechat = False
    acc = os.path.join(_weixin_state_dir(), "account.json")
    try:
        data = _load_json(acc)
        wechat = bool(data.get("token"))
    except Exception:
        pass

    dingtalk = False
    cfg = _load_json(_config_path())
    dt = cfg.get("channels", {}).get("dingtalk", {})
    dingtalk = dt.get("enabled", False) and bool(dt.get("clientId"))

    return {"wechat": {"bound": wechat}, "dingtalk": {"bound": dingtalk}}
