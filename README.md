# cloud-agent-gateway

Framework-agnostic cloud deployment layer for AI agents — pip-installable sidecar.

## 定位

`cloud-agent-gateway` 是一个轻量级 pip 包，提供 AI agent 框架在多云平台（HF Spaces、ModelScope Studio）上部署所需的**平台抽象、OAuth 代理、身份注入、中继连接**等通用能力。它不绑定任何特定 agent 框架——通过 `PlatformProtocol` 接口，任何框架都能接入。

> 实际生产参考：[nanobot-legion](https://github.com/DreamShepherd2006/nanobot-legion) — 基于 `cloud-agent-gateway` 的 nanobot 多智能体部署层。

## 平台支持

| 平台 | 类 | OAuth | Squad Relay | 备注 |
|---|---|---|---|---|
| HF Staging | `HFStagingPlatform` | ✅ | ✅ | 完整 OAuth + WS 身份注入 |
| HF Direct | `HFDirectPlatform` | — | ✅ | 仅 relay，无 OAuth |
| HF Spaces | `HFSpacesPlatform` | ✅ | ✅ | HF OAuth via authlib |
| ModelScope | `ModelScopePlatform` | ✅ | ✅ | MS OAuth + 路由绕过 |
| ModelScope Squad | `ModelScopeSquadPlatform` | ✅ | ✅ | 内部 squad 变体 |

## 核心能力

### 1. 平台探测与抽象（`PlatformProtocol`）

```python
from cloud_agent_gateway.platforms import platform

platform.PLATFORM_NAME   # → "hf_spaces" | "modelscope" | ...
platform.is_hf            # → True / False
platform.can_oauth        # → True / False
platform.instance_path()  # → "/data/instances/neo" (平台感知路径)
```

所有平台差异（路径、环境变量、OAuth 流）封装在对应子类中，调用方无需 `if-else` 分支。

### 2. OAuth 代理

`OAuthProxy` 提供统一的认证流程：

```python
from cloud_agent_gateway.oauth_proxy import OAuthProxy

proxy = OAuthProxy(platform, app)
proxy.mount_routes()  # /api/auth/login, /api/auth/callback, /api/auth/user
```

- **HF Spaces**: 通过 `authlib` 对接 HF OAuth2，注入 `x-forwarded-*` 头绕过代理限制
- **ModelScope Studio**: OAuth 回调路径适配 `/api/auth/callback`，处理平台代理 header 剥离
- 用户身份解析后注入 `X-Nanobot-Sender-ID` / `X-Nanobot-Sender-Name` header

### 3. Relay Token 映射

云平台环境中 token 以环境变量形式注入，命名规则：

```
SQUAD_RELAY_TOKEN_{PLATFORM}_{space_name}
```

例如：
- `SQUAD_RELAY_TOKEN_HF_nanobot_cloud_demo`
- `SQUAD_RELAY_TOKEN_MS_ms_nanobot_cloud_demo`

`platform_setup.py` 在启动时自动探测平台、展开环境变量、写入 shell profile。

### 4. 身份注入（Identity Injection）

平台代理通常会剥离 `Authorization` 等自定义 header。gatekeeper 利用 platform 能力在应用层注入身份，无需依赖原始 header。

```python
# gatekeeper 注入 sender_id 到 WebSocket envelope
envelope["sender_id"] = user_info["sub"]
envelope["sender_name"] = user_info.get("name", "")
```

配合上游 `target_chat_id` PR（#4139）实现刷新恢复会话。

### 5. Header 剥离感知

平台代理会剥离/改写以下 header：
- `Authorization` → 移除
- `Content-Length` → ModelScope 注入 0，导致部分 HTTP 库拒绝响应

`PlatformProtocol` 提供 `strip_response_headers` 方法，平台子类声明需要剥离的 header，gatekeeper 自动处理。

## 安装

```bash
pip install cloud-agent-gateway
```

## 使用

### 作为库（嵌入到 gatekeeper 应用）

```python
from cloud_agent_gateway.platforms import platform
from cloud_agent_gateway.oauth_proxy import OAuthProxy

# 平台自动探测（DEPLOY_PLATFORM 环境变量）
print(f"Running on {platform.PLATFORM_NAME}")

# 挂载 OAuth 路由
proxy = OAuthProxy(platform, app)
proxy.mount_routes()

# 注入身份到 WebSocket envelope
# → 见 nanobot-legion gatekeeper.py 实现
```

### 作为 CLI（平台初始化）

```bash
# 写入 platform.sh（RELAY_TOKEN 等）
cloud-gateway-setup

# 启动入口
cloud-agent-gateway
```

## 架构

```
                   ┌─────────────────────────────┐
                   │     cloud-agent-gateway       │
                   │     (pip 包, 框架无关)          │
                   │                               │
    WebSocket ← →  │  OAuthProxy  │  PlatformProtocol │ ← → 平台 API
                   │  Relay Mgr   │  PlatformSetup     │
                   └──────────┬──────────────────────┘
                              │ pip install
                   ┌──────────▼──────────────────────┐
                   │      nanobot-legion              │
                   │      (nanobot 专用)               │
                   │                                  │
                   │  Gatekeeper  │  Squad Bridge     │
                   │  Patches     │  Dockerfile       │
                   └──────────────────────────────────┘
```

## 许可证

MIT

## 相关

- [nanobot-legion](https://github.com/DreamShepherd2006/nanobot-legion) — 生产级参考实现
- [HKUDS/nanobot](https://github.com/HKUDS/nanobot) — 底层 agent 框架
- [PR #4139](https://github.com/HKUDS/nanobot/pull/4139) — `target_chat_id` 会话恢复（配合身份注入使用）
