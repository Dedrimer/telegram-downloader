# Telegram Downloader

[English](#english) | [中文](#中文)

---

## English

A simple Telegram bot for downloading video files with support for media group batch downloads.

### Features

- ✅ Single file download with confirmation
- ✅ **Media group batch download** - Download multiple files with one click
- ✅ Large file support via local Bot API
- ✅ Original file name preservation
- ✅ Docker deployment

### Quick Start

1. **Clone and configure**:
   ```bash
   git clone https://github.com/avibn/telegram-downloader.git
   cd telegram-downloader
   cp .example.env .env
   # Edit .env with your settings
   ```

2. **Run with Docker**:
   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```

3. **Start downloading**:
   - Send a file to the bot
   - Click "Yes" to download
   - For media groups, all files download at once!

### Environment Variables

| Variable | Description |
|----------|-------------|
| `BOT_TOKEN` | Telegram bot token |
| `LOCAL_BOT_API_URL` | Local Bot API URL (default: `http://127.0.0.1:8081`) |
| `BOT_API_DIR` | Bot API storage directory |
| `DOWNLOAD_TO_DIR` | Download output directory |
| `USER_ID` | Your Telegram user ID |
| `CHAT_ID` | Chat ID for bot operation |

### Commands

- `/start` - Start the bot
- `/help` - Show help
- `/status` - Check download status
- `/info` - Get user/chat info
- `/storage` - Check storage space

---

## 中文

一个简单的 Telegram 机器人，用于下载视频文件，支持媒体组批量下载。

### 功能特点

- ✅ 带确认的单文件下载
- ✅ **媒体组批量下载** - 一次点击下载多个文件
- ✅ 通过本地 Bot API 支持大文件
- ✅ 保持原始文件名
- ✅ Docker 部署

### 快速开始

1. **克隆并配置**:
   ```bash
   git clone https://github.com/avibn/telegram-downloader.git
   cd telegram-downloader
   cp .example.env .env
   # 编辑 .env 文件设置您的配置
   ```

2. **使用 Docker 运行**:
   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```

3. **开始下载**:
   - 发送文件给机器人
   - 点击 "Yes" 下载
   - 对于媒体组，所有文件一次性下载！

### 环境变量

| 变量名 | 描述 |
|--------|------|
| `BOT_TOKEN` | Telegram 机器人令牌 |
| `LOCAL_BOT_API_URL` | 本地 Bot API URL（默认：`http://127.0.0.1:8081`） |
| `BOT_API_DIR` | Bot API 存储目录 |
| `DOWNLOAD_TO_DIR` | 下载输出目录 |
| `USER_ID` | 您的 Telegram 用户 ID |
| `CHAT_ID` | 机器人操作的聊天 ID |

### 命令

- `/start` - 启动机器人
- `/help` - 显示帮助
- `/status` - 检查下载状态
- `/info` - 获取用户/聊天信息
- `/storage` - 检查存储空间

---

## 📦 媒体组功能

### 如何使用

1. **转发多个文件**:
   - 在 Telegram 中选择多个文件
   - 一起转发给机器人

2. **确认下载**:
   - 机器人会显示所有文件列表
   - 显示总大小
   - 点击 "Yes" 一次性下载所有文件

3. **下载完成**:
   - 每个文件独立下载
   - 显示成功/失败统计
   - 所有文件保存到指定目录

### 示例

```
您确定要下载 3 个文件吗？

📄 document1.pdf (2.50 MB)
📄 document2.pdf (1.80 MB)
📄 document3.pdf (3.20 MB)

💾 总大小: 7.50 MB

[Yes] [No]
```

点击 "Yes" 后：

```
✅ 批量下载完成

✅ 成功: 3
❌ 失败: 0
📁 总计: 3
```

---

## 🐳 Docker 部署

### 生产环境

```bash
docker compose -f docker-compose.prod.yml up -d
```

### 本地开发

```bash
# 只运行本地 Bot API
docker compose -f docker-compose.api.yml up -d

# 运行机器人
python run.py
```

### 查看日志

```bash
docker logs -f telegram-downloader-bot
```

---

## 🔧 故障排除

### 机器人无响应

1. 检查 `BOT_TOKEN` 是否正确
2. 确认机器人正在运行：`docker ps`
3. 查看日志获取错误信息

### 媒体组未检测到

1. 确保文件是作为组一起转发的
2. 检查文件类型是否支持
3. 查看日志中的检测消息

### 下载失败

1. 检查存储空间：`/storage`
2. 验证目录权限
3. 检查网络连接

---

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

---

## 🙏 支持

如有问题，请[创建 Issue](https://github.com/avibn/telegram-downloader/issues)