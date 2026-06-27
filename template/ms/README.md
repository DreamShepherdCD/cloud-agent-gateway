# 🤖 一键部署个人 AI 助手（ModelScope）

## 使用方法

1. 在 [ModelScope 创空间](https://modelscope.cn/studios) 创建新空间，SDK 类型选 **Docker**
2. 上传本目录下的文件到空间（`Dockerfile` 必需，`README.md` 可选）
3. 等待构建完成 → 打开空间 → 填写 LLM + OAuth 配置 → 开始使用
4. OAuth 需**手动创建**应用（setup 页有操作指引）

## 文件说明

| 文件 | 作用 |
|------|------|
| `Dockerfile` | 从 GitHub 安装 CAG 框架 + nanobot |
| `entrypoint.sh` | 启动时检测配置：无配置 → setup 页 / 有配置 → 正常运行 |
| `config.template.json` | 空壳模板，触发 setup 模式 |
| `README.md` | 空间展示页（可选上传） |

## 工作流程

```
打开空间 → 检测配置状态
    ├─ 无 oauth.json → Phase 1 配置页（填 API Key / 模型 / OAuth 凭证）
    └─ 有 oauth.json → Phase 2 正常运行（OAuth + 通道绑定）
```

## 重新配置

1. 浏览器访问 `https://你的空间地址/reset-setup`（仅删除 OAuth，API Key 保留）
2. 空间**停止 → 启动**
3. 重新进入配置页（已有 API Key 会预填）
