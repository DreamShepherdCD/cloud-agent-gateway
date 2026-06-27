---
title: nanobot-cloud-demo
emoji: ☁️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
hf_oauth: true
pinned: false
---

# 🤖 一键部署个人 AI 助手（HuggingFace）

## 使用方法

1. 创建 [Docker Space](https://huggingface.co/new-space?sdks=docker)
2. 上传 `Dockerfile` + 本 `README.md` 到空间根目录
3. 等待构建完成 → 打开空间 → 填写 LLM 配置 → 开始使用
4. OAuth 由 HuggingFace **自动配置**（`hf_oauth: true`），无需手动创建 OAuth 应用

## 文件说明

| 文件 | 作用 |
|------|------|
| `Dockerfile` | 从 GitHub 安装 CAG 框架 + nanobot |
| `entrypoint.sh` | 启动时检测配置：无配置 → setup 页 / 有配置 → 正常运行 |
| `config.template.json` | 空壳模板，触发 setup 模式 |
| `README.md` | 空间展示页 + HF OAuth 自动配置元数据 |

## 工作流程

```
打开空间 → 检测配置状态
    ├─ 无 oauth.json → Phase 1 配置页（填 API Key / 模型）
    └─ 有 oauth.json → Phase 2 正常运行（OAuth + 通道绑定）
```

> HF 上 OAuth 自动注入，Phase 1 不需要手动填写 OAuth 凭证。

## 重新配置

1. 浏览器访问 `https://你的空间地址/reset-setup`（仅删除 OAuth，API Key 保留）
2. 空间**停止 → 启动**
3. 重新进入配置页（已有 API Key 会预填）
