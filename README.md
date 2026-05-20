# Telegram Downloader 📁

[English](#english) | [中文](#中文)

---

## English

A Telegram bot for downloading video files sent or forwarded to the bot, with support for batch downloading of media groups.

### ✨ Features

- **Single File Download**: Download individual files with confirmation
- **Media Group Batch Download**: Download multiple files from a media group with a single confirmation
- **Large File Support**: Leverages local Telegram Bot API server for large file downloads
- **Original File Names**: Maintains original file names during download
- **Simple Setup**: Easy Docker-based deployment
- **Progress Tracking**: Monitor download status in real-time

### 📖 Table of Contents

- [About](#about)
- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
- [Usage](#usage)
- [Media Group Feature](#media-group-feature)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

### About

This project is a Telegram bot designed for personal use, leveraging the [local Telegram Bot API server](https://github.com/tdlib/telegram-bot-api) to download large video files sent or forwarded to the bot, directly to a specified local directory.

It's a simple solution that doesn't require a desktop or graphical client, and maintains the original file name. It's particularly useful for forwarding large video files 🎬 to download onto a NAS system.

### Quick Start

#### Docker Setup (Recommended)

Using Docker is the easiest way to set this up. Follow these steps:

1. **Prerequisites**: Ensure Docker and Docker Compose are installed on your system.

2. **Clone Repository**:
   ```bash
   git clone https://github.com/avibn/telegram-downloader.git
   cd telegram-downloader
   ```

3. **Create Environment File**:
   ```bash
   cp .example.env .env
   ```
   
   Edit the `.env` file with your configuration (see [Environment Variables](#environment-variables)).

4. **Run with Docker**:
   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```

5. **Verify Installation**:
   ```bash
   docker ps
   ```

#### Manual Setup

If you prefer a manual setup:

1. **Install Dependencies**:
   ```bash
   # Using uv (recommended)
   pip install uv
   uv install
   
   # Or using pip
   pip install -r requirements.txt
   ```

2. **Configure Environment**:
   ```bash
   cp .example.env .env
   # Edit .env with your settings
   ```

3. **Run the Bot**:
   ```bash
   python run.py
   ```

### Environment Variables

Create a `.env` file with the following variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `BOT_TOKEN` | Telegram bot token from [@BotFather](https://t.me/botfather) | `123456789:ABCdef...` |
| `LOCAL_BOT_API_URL` | Local Bot API server URL | `http://127.0.0.1:8081` |
| `BOT_API_DIR` | Directory for Bot API storage | `./bot-api/` |
| `DOWNLOAD_TO_DIR` | Directory for downloaded files | `./downloads/` |
| `USER_ID` | Your Telegram user ID | `1234567890` |
| `CHAT_ID` | Chat ID for bot operation | `1234567890` |
| `TELEGRAM_API_ID` | Telegram API ID (for local API) | `12345678` |
| `TELEGRAM_API_HASH` | Telegram API Hash (for local API) | `abcdef1234...` |
| `TELEGRAM_LOCAL` | Enable local API mode | `true` |

### Usage

#### Single File Download

1. Send or forward a file to the bot
2. The bot will show a confirmation message with file details
3. Click **Yes** to download or **No** to cancel
4. Download progress and completion will be reported

#### Media Group Batch Download

The **Media Group** feature allows you to download multiple files from a single media group with just one confirmation.

1. **How it works**:
   - When you forward a media group (multiple files), the bot detects all files
   - Shows a single confirmation message listing all files
   - Downloads all files at once when confirmed

2. **Example**:
   - Forward a media group with 3 PDF files
   - Bot shows: "Are you sure you want to download 3 files?"
   - Lists all files with their sizes
   - Click **Yes** to download all at once

3. **Special Commands**:
   - `/status`: Check current download status
   - `/info`: Get user and chat information
   - `/storage`: Check available storage
   - `/help`: Show all commands

### Media Group Feature

The media group feature uses a timer-based approach to collect all files:

1. **Detection**: When a message arrives with `media_group_id`, it's identified as part of a group
2. **Collection**: A 0.5-second timer starts, collecting all files in the same group
3. **Confirmation**: After the timer expires, shows a single confirmation with all files
4. **Batch Download**: Downloads all files with individual progress tracking
5. **Statistics**: Shows download success/failure count after completion

### Troubleshooting

#### Common Issues

1. **Bot not responding**:
   - Verify `BOT_TOKEN` is correct
   - Check bot is running with `docker ps`
   - Review logs: `docker logs telegram-downloader-bot`

2. **Files not downloading**:
   - Ensure `BOT_API_DIR` exists and is writable
   - Check available storage space
   - Verify local Bot API server is accessible

3. **Media group not detected**:
   - Files must be forwarded together as a group
   - Some file types may not be supported
   - Check bot logs for detection messages

#### Debug Mode

Enable debug logging by setting:
```bash
LOG_LEVEL=DEBUG
```

### Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 中文

用于下载发送或转发给机器人的视频文件的 Telegram 机器人，支持媒体组的批量下载功能。

### ✨ 功能特点

- **单文件下载**: 带确认的单个文件下载
- **媒体组批量下载**: 一次确认下载媒体组中的多个文件
- **大文件支持**: 利用本地 Telegram Bot API 服务器下载大文件
- **原始文件名**: 下载时保持原始文件名
- **简单部署**: 基于 Docker 的简单部署
- **进度跟踪**: 实时监控下载状态

### 📖 目录

- [关于](#关于)
- [快速开始](#快速开始)
- [环境变量](#环境变量)
- [使用方法](#使用方法)
- [媒体组功能](#媒体组功能)
- [故障排除](#故障排除)
- [贡献](#贡献)
- [许可证](#许可证)

### 关于

这个项目是为个人使用设计的 Telegram 机器人，利用[本地 Telegram Bot API 服务器](https://github.com/tdlib/telegram-bot-api)将发送或转发给机器人的大型视频文件直接下载到指定的本地目录。

这是一个简单的解决方案，不需要桌面或图形客户端，并且保持原始文件名。特别适合将大型视频文件 🎬 转发下载到 NAS 系统。

### 快速开始

#### Docker 部署（推荐）

使用 Docker 是最简单的部署方式：

1. **前提条件**: 确保系统已安装 Docker 和 Docker Compose。

2. **克隆仓库**:
   ```bash
   git clone https://github.com/avibn/telegram-downloader.git
   cd telegram-downloader
   ```

3. **创建环境文件**:
   ```bash
   cp .example.env .env
   ```
   
   编辑 `.env` 文件，配置您的设置（参见[环境变量](#环境变量)）。

4. **运行 Docker**:
   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```

5. **验证安装**:
   ```bash
   docker ps
   ```

#### 手动部署

如果您更喜欢手动部署：

1. **安装依赖**:
   ```bash
   # 使用 uv（推荐）
   pip install uv
   uv install
   
   # 或使用 pip
   pip install -r requirements.txt
   ```

2. **配置环境**:
   ```bash
   cp .example.env .env
   # 编辑 .env 文件设置您的配置
   ```

3. **运行机器人**:
   ```bash
   python run.py
   ```

### 环境变量

创建 `.env` 文件，包含以下变量：

| 变量名 | 描述 | 示例 |
|--------|------|------|
| `BOT_TOKEN` | 从 [@BotFather](https://t.me/botfather) 获取的 Telegram 机器人令牌 | `123456789:ABCdef...` |
| `LOCAL_BOT_API_URL` | 本地 Bot API 服务器 URL | `http://127.0.0.1:8081` |
| `BOT_API_DIR` | Bot API 存储目录 | `./bot-api/` |
| `DOWNLOAD_TO_DIR` | 下载文件存储目录 | `./downloads/` |
| `USER_ID` | 您的 Telegram 用户 ID | `1234567890` |
| `CHAT_ID` | 机器人操作的聊天 ID | `1234567890` |
| `TELEGRAM_API_ID` | Telegram API ID（用于本地 API） | `12345678` |
| `TELEGRAM_API_HASH` | Telegram API Hash（用于本地 API） | `abcdef1234...` |
| `TELEGRAM_LOCAL` | 启用本地 API 模式 | `true` |

### 使用方法

#### 单文件下载

1. 发送或转发文件给机器人
2. 机器人会显示包含文件详细信息的确认消息
3. 点击 **Yes** 下载或 **No** 取消
4. 下载进度和完成情况会实时报告

#### 媒体组批量下载

**媒体组**功能允许您只需一次确认即可下载媒体组中的多个文件。

1. **工作原理**:
   - 当您转发媒体组（多个文件）时，机器人会检测所有文件
   - 显示包含所有文件列表的单个确认消息
   - 确认后同时下载所有文件

2. **示例**:
   - 转发包含 3 个 PDF 文件的媒体组
   - 机器人显示："您确定要下载 3 个文件吗？"
   - 列出所有文件及其大小
   - 点击 **Yes** 一次性下载所有文件

3. **特殊命令**:
   - `/status`: 检查当前下载状态
   - `/info`: 获取用户和聊天信息
   - `/storage`: 检查可用存储空间
   - `/help`: 显示所有命令

### 媒体组功能

媒体组功能使用基于定时器的方法收集所有文件：

1. **检测**: 当消息到达时带有 `media_group_id`，识别为媒体组的一部分
2. **收集**: 启动 0.5 秒定时器，收集同一组中的所有文件
3. **确认**: 定时器到期后，显示包含所有文件的单个确认消息
4. **批量下载**: 同时下载所有文件，每个文件独立跟踪进度
5. **统计**: 完成后显示下载成功/失败数量

### 故障排除

#### 常见问题

1. **机器人无响应**:
   - 验证 `BOT_TOKEN` 是否正确
   - 检查机器人是否正在运行：`docker ps`
   - 查看日志：`docker logs telegram-downloader-bot`

2. **文件未下载**:
   - 确保 `BOT_API_DIR` 存在且可写
   - 检查可用存储空间
   - 验证本地 Bot API 服务器可访问

3. **媒体组未检测到**:
   - 文件必须作为组一起转发
   - 某些文件类型可能不支持
   - 检查机器人日志中的检测消息

#### 调试模式

启用调试日志：
```bash
LOG_LEVEL=DEBUG
```

### 贡献

欢迎贡献！请随时提交 Pull Request。

1. Fork 仓库
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

### 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

---

## 📊 功能对比

| 功能 | 单文件下载 | 媒体组下载 |
|------|------------|------------|
| 确认次数 | 每个文件一次 | 所有文件一次 |
| 下载方式 | 顺序下载 | 并发下载 |
| 进度显示 | 单个文件进度 | 整体进度 |
| 错误处理 | 文件独立处理 | 文件独立处理 |
| 适用场景 | 单个文件 | 多个文件 |

## 🔧 技术栈

- **Python 3.11+**
- **python-telegram-bot**: Telegram Bot API 封装
- **Docker**: 容器化部署
- **asyncio**: 异步并发处理

## 📝 更新日志

### v1.1.0 - 媒体组批量下载功能

- ✨ 新增媒体组检测和批量下载功能
- ✨ 使用定时器机制收集媒体组文件
- ✨ 支持一次确认下载多个文件
- ✨ 添加下载统计信息显示
- 📝 更新 README 中英文版本
- 🧪 添加完整的测试用例

### v1.0.0 - 基础功能

- ✨ 单文件下载功能
- ✨ 文件确认和取消功能
- ✨ 下载进度跟踪
- ✨ Docker 部署支持

## 🙏 致谢

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) - Telegram Bot API 封装
- [local-bot-api](https://github.com/tdlib/telegram-bot-api) - 本地 Telegram Bot API 服务器
- [Docker](https://www.docker.com/) - 容器化平台

## 📞 支持

如果您遇到任何问题，请[创建 Issue](https://github.com/avibn/telegram-downloader/issues)。

---

**Made with ❤️ for the Telegram community**