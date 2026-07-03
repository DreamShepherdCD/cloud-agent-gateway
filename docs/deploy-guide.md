# nanobot 云端部署傻瓜指南

只需 4 步：创建空间 → 挂载存储 → 上传文件 → 打开链接。不用装任何软件。

---

## 方式一：HuggingFace Spaces（推荐，最简单）

### 第 1 步：创建空间

1. 打开 https://huggingface.co/new-space
2. 用你的 HuggingFace 账号登录（没有就注册一个，免费）
3. 填写以下信息：

| 字段 | 填写内容 |
|:---|:---|
| Space Name | 随便填，比如 `my-nanobot` |
| License | 选 `mit` |
| Space SDK | 选 **Docker** → 再选 **Blank** |
| Space Hardware | 选免费的 **CPU basic · 2 vCPU · 16 GB** |

4. 点击 **Create Space** 按钮

### 第 2 步：挂载持久存储（重要！不然后面配置会丢）

HF Spaces 容器重启后默认不保留数据。需要挂一个 **Storage Bucket** 来持久化你的配置和账号：

1. 进入空间页面 → 点击 **Settings** 标签
2. 找到 **Storage** 区域 → 点击 **Attach a storage bucket**
3. 填写以下信息：

| 字段 | 填写内容 |
|:---|:---|
| Bucket | 如果没有，点击创建新存储罐，随便命名（如 `my-nanobot-data`） |
| Bucket visibility | 选 **Private**（你的配置和 API Key 不想公开） |
| Mount path | 填 `/data` |
| Access mode | 选 **Read & Write** |

4. 点击 **Mount** 确认

> ⚠️ 没做这一步的话，容器每次重建后 setup 表单、OAuth 凭证、通道绑定都会丢失。

### 第 3 步：上传 Dockerfile

1. 创建完成后，页面会显示一个文件列表（空的）
2. 点击 **Add file** 按钮 → 选择 **Create a new file**
3. 文件名填写 `Dockerfile`（注意首字母大写，没有后缀）
4. 打开这个链接，复制里面的全部内容：

   👉 https://raw.githubusercontent.com/DreamShepherd2006/cloud-agent-gateway/main/Dockerfile

   （这是 cloud-agent-gateway 官方仓库维护的 Dockerfile，始终是最新版本）

5. 粘贴到文件内容框里
6. 点击 **Commit new file** 保存
7. 空间会自动开始构建（约 2-5 分钟）

### 第 4 步：打开你的 nanobot

1. 构建完成后，页面顶部会出现一个 **App** 按钮或链接
2. 点击它 → 进入 nanobot 的 setup 页面
3. 填写你的 LLM API Key 和 OAuth 信息
4. 提交后，按提示**重启空间**（Settings → Factory Rebuild）
5. 再次打开链接 → OAuth 登录 → 进入 nanobot！

> 💡 **以后怎么用？** 直接打开 `https://huggingface.co/spaces/你的用户名/my-nanobot` 就行。给家人朋友也发这个链接。

---

## 方式二：ModelScope 魔搭社区

> ⚠️ ModelScope 的 Docker 空间要求**绑定阿里云账号并完成实名认证**，请提前准备好。

### 第 1 步：创建空间

1. 打开 https://www.modelscope.cn/studios/create
2. 用你的 ModelScope 账号登录（没有就注册一个，免费）
3. 填写以下信息：

| 字段 | 填写内容 |
|:---|:---|
| 空间名称 | 随便填，比如 `my-nanobot` |
| 空间 SDK | 选择 **Docker** |
| 其他 | 保持默认 |

4. 点击 **创建空间**

### 第 2 步：上传 Dockerfile

创建完空间后，页面会自动进入部署引导：

1. 页面上会提示「本空间还未完成首次内容部署」→ 点击 **部署引导** 按钮
2. 进入上传界面，看到「请上传空间文件/文件夹」
3. 先准备好 Dockerfile：
   - 打开 👉 https://raw.githubusercontent.com/DreamShepherd2006/cloud-agent-gateway/main/Dockerfile
   - 在页面空白处**右键 → 另存为**（或复制全部内容）
   - 文件名保存为 `Dockerfile`（没有后缀）
4. 上传这个 `Dockerfile` 文件

### 第 3 步：等待构建

1. 上传 Dockerfile 后，系统自动开始部署，无需额外操作
2. 等待约 3-6 分钟构建完成（可在页面右侧查看日志）
3. 构建成功后空间自动上线，状态变为 **运行中**

### 第 4 步：打开你的 nanobot

1. 点击空间链接（格式：`https://modelscope.cn/studios/你的用户名/my-nanobot/summary`）
2. 进入 nanobot 的 setup 页面
3. 填写你的 LLM API Key 和 OAuth 信息
4. 提交后，按提示**重启空间**：页面右侧「空间管理」→「重新部署」→ 点「确认部署」
5. 再次打开链接 → OAuth 登录 → 进入 nanobot！

---

## 常见问题

### Q: 我没有 API Key 怎么办？

可以去以下平台注册获取（都有免费额度）：

| 服务商 | 获取地址 | 推荐模型 |
|:---|:---|:---|
| DeepSeek | https://platform.deepseek.com | `deepseek-chat` |
| 硅基流动 | https://siliconflow.cn | `deepseek-ai/DeepSeek-V3` |
| 智谱 | https://open.bigmodel.cn | `glm-4-flash` |

### Q: OAuth 信息是什么？怎么填？

- **HuggingFace**：空间如果启用了 OAuth，会自动注入凭证，不需要手动填
- **ModelScope**：setup 页面有详细提示，照着做就行（会告诉你填什么、在哪填）

### Q: 构建失败怎么办？

1. 检查 Dockerfile 是否完整复制，文件名是否是 `Dockerfile`（没有 `.txt` 后缀）
2. **HuggingFace**：在空间设置里点 **Factory Rebuild** 重试
3. **ModelScope**：在页面右侧「空间管理」→「重新部署」→ 点「确认部署」重试
4. 看构建日志找具体错误

### Q: 空间会一直运行吗？

- **HuggingFace**：免费空间长时间不活跃会自动休眠，有人访问时自动唤醒（几秒延迟）
- **ModelScope**：免费空间持续运行

### Q: 我的数据安全吗？

- **HuggingFace**：通过 Storage Bucket（挂载到 `/data`）持久化所有数据，容器重建不影响
- **ModelScope**：数据存放在 `/mnt/workspace`（平台提供的持久化目录），重启/重建不会删除
- 配置（API Key、OAuth 凭证）、对话记录、通道绑定凭证均持久保存
- 只有删除空间本身才会清除数据
- API Key 由你填入，不会泄露给第三方

### Q: 能绑定微信/QQ 吗？

能。登录 nanobot WebUI 后，侧边栏有「系统配置」入口，里面有微信、QQ、飞书、钉钉的绑定指引，扫码即用。

---

## 一条命令（给会用终端的人）

如果你有终端和 Git，一条命令就够：

```bash
# 克隆模板仓库，只需 Dockerfile 这一个文件
git clone https://github.com/DreamShepherd2006/cloud-agent-gateway.git
# 把仓库里的 Dockerfile 上传到你的 HF Space 或 ModelScope Space
```

模板仓库里还有更详细的配置选项和说明。
