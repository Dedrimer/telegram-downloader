# Telegram Downloader 📁

[中文版](README_CN.md)

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
| `APP_SETTINGS_FILE` | Runtime settings JSON path | `./data/settings.json` |
| `SINGLE_FILE_GROUP_ENABLED` | Enable consecutive single-file grouping at startup | `false` |
| `SINGLE_FILE_GROUP_DELAY` | Single-file grouping wait time in seconds | `1.0` |
| `DOWNLOAD_STATUS_UPDATE_INTERVAL` | Download status update interval in seconds (minimum 3.0) | `5.0` |
| `MAX_CONCURRENT_DOWNLOADS` | Bot API file download concurrency, capped at 1 for low-memory devices | `1` |
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
   - Downloads the selected files one by one when confirmed

2. **Example**:
   - Forward a media group with 3 PDF files
   - Bot shows: "Are you sure you want to download 3 files?"
   - Lists all files with their sizes
   - Click **Yes** to start the sequential batch

3. **Special Commands**:
   - `/status`: Check current download status
   - `/info`: Get user, chat, and container version information
   - `/storage`: Check available storage space
   - `/single_group on [seconds]`: Group consecutive single-file messages, e.g. `/single_group on 1.5`
   - `/single_group off`: Disable consecutive single-file grouping
   - `/help`: Show all commands

### Media Group Feature

The media group feature uses a timer-based approach to collect all files:

1. **Detection**: When a message arrives with `media_group_id`, it's identified as part of a group
2. **Collection**: A 0.5-second timer starts, collecting all files in the same group
3. **Confirmation**: After the timer expires, shows a single confirmation with all files
4. **Batch Download**: Downloads files sequentially with individual progress tracking
5. **Statistics**: Shows download success/failure count after completion

When `/single_group` is enabled, consecutive single-file messages without a `media_group_id` are collected per chat. Each new single-file message resets the timer; when no new file arrives before the delay expires, the bot reuses the media-group confirmation, file selection, and batch download flow.

Runtime settings are persisted in `data/settings.json` when changed through bot commands. The compose files mount `./data` to `/app/data`; if the JSON file exists, it overrides the environment defaults for saveable settings such as single-file grouping and download status update interval.

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

## 📊 Feature Comparison

| Feature | Single File Download | Media Group Download |
|---------|---------------------|----------------------|
| Confirmation | Once per file | Once for all files |
| Download Method | Sequential | Sequential |
| Progress Display | Single file progress | Overall progress |
| Error Handling | Per-file independent | Per-file independent |
| Use Case | Single file | Multiple files |

## 🔧 Tech Stack

- **Python 3.11+**
- **python-telegram-bot**: Telegram Bot API wrapper
- **Docker**: Containerized deployment
- **asyncio**: Async update and download orchestration

## 📝 Changelog

### v1.1.0 - Media Group Batch Download Feature

- ✨ Added media group detection and batch download
- ✨ Timer mechanism to collect media group files
- ✨ Download multiple files with one confirmation
- ✨ Added download statistics display
- 📝 Updated README English version

### v1.0.0 - Basic Features

- ✨ Single file download
- ✨ File confirmation and cancel functionality
- ✨ Download progress tracking
- ✨ Docker deployment support

## 🙏 Acknowledgments

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) - Telegram Bot API wrapper
- [local-bot-api](https://github.com/tdlib/telegram-bot-api) - Local Telegram Bot API server
- [Docker](https://www.docker.com/) - Containerization platform

## 📞 Support

If you encounter any issues, please [create an Issue](https://github.com/avibn/telegram-downloader/issues).

---

**Made with ❤️ for the Telegram community**
