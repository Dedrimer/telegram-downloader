# Agent Guide

This repository contains a Python Telegram bot that downloads files sent or forwarded to it. It is intended for personal/NAS-style use and is designed to work with a local Telegram Bot API server so large files can be downloaded to a local directory while preserving the original file name.

## Project Snapshot

- Runtime: Python 3.11+
- Main framework: `python-telegram-bot`
- Configuration: `.env` loaded through `pydantic-settings` in `src/utils/env.py`
- Entrypoint: `python run.py`
- Docker entrypoint: `uv run python run.py`
- Main bot setup: `src/bot.py`
- Command and message handlers: `src/cogs/`
- Shared middleware/decorators: `src/middlewares/`
- Download state model: `src/models/downloading_file.py`
- File/media helpers: `src/utils/`

## Important Commands

Install dependencies:

```bash
pip install -r requirements.txt
```

Or, with uv:

```bash
uv sync
```

Run locally:

```bash
python run.py
```

Run the local Telegram Bot API service only:

```bash
docker compose -f docker-compose.api.yml up -d
```

Run the local build with Bot API service:

```bash
docker compose -f docker-compose.local.yml up -d
```

Run the published production image:

```bash
docker compose -f docker-compose.prod.yml up -d
```

Lint if `ruff` is installed:

```bash
uv run ruff check .
```

There are currently no committed test files in `tests/`.

## Required Environment

Create `.env` from `.example.env`. Required bot settings are validated by `src/utils/env.py`:

- `BOT_TOKEN`
- `LOCAL_BOT_API_URL`
- `BOT_API_DIR`
- `DOWNLOAD_TO_DIR`
- `USER_ID`
- `CHAT_ID`

Docker compose files also expect these local Bot API settings:

- `TELEGRAM_API_ID`
- `TELEGRAM_API_HASH`
- `TELEGRAM_LOCAL`

Do not commit real tokens, Telegram API credentials, user IDs, or private chat IDs.

## Architecture Notes

`run.py` configures logging and calls `src.bot.main()`.

`src/bot.py` builds a `telegram.ext.Application` with:

- `concurrent_updates(True)`
- `local_mode(True)`
- `base_url(f"{LOCAL_BOT_API_URL}/bot")`
- `base_file_url(f"{LOCAL_BOT_API_URL}/file/bot")`

The bot registers handlers from `src/cogs/general.py` and `src/cogs/downloader.py`, plus the error handler from `src/cogs/error_handler.py`.

Handler decorators live in `src/middlewares/handlers.py`. Authorization is enforced with `@auth_required` from `src/middlewares/auth.py`, which checks both `USER_ID` and `CHAT_ID`.

## Download Flow

Single-file downloads are handled in `src/cogs/downloader.py`:

1. `download()` receives document/video/audio messages.
2. The bot asks for confirmation with inline buttons.
3. `button()` handles callback queries.
4. `_download_single_file()` calls `get_file()` and moves the downloaded file from the local Bot API directory into `DOWNLOAD_TO_DIR`.
5. Active downloads are tracked in the global `downloading_files` dict from `src/models/downloading_file.py`.

Media groups are collected in `src/utils/media_group.py`:

1. Messages sharing a `media_group_id` are buffered.
2. A short async timer waits for all group messages to arrive.
3. The downloader shows one confirmation message for the group.
4. The user can download all files or open the file selection UI.

The downloader also supports:

- `/status` display for active downloads
- cancelling active downloads from status messages
- cancelling individual downloads from the download status message
- retrying failed single downloads
- retrying failed media group files
- paginated selection UI for large media groups

## Source Conventions

- This is an async bot. New Telegram handlers should be `async def` and use the existing decorators in `src/middlewares/handlers.py`.
- Apply `@auth_required` to handlers that perform private operations or expose local state.
- Keep callback data short enough for Telegram callback query limits.
- Escape user-controlled file names and error strings before using Telegram Markdown. Existing helpers in `src/cogs/downloader.py` include `escape_md()` and `escape_md2()`.
- Be careful with global in-memory state in `src/cogs/downloader.py`; the app enables concurrent updates.
- Downloaded files are first materialized by the local Bot API server, then moved into `DOWNLOAD_TO_DIR`.
- Preserve original file names when possible. If Telegram media has no file name, existing code derives one from `file_id` and MIME/video type.
- Avoid broad refactors in `src/cogs/downloader.py` unless the task specifically calls for it; it contains most user-facing behavior and several callback flows.

## Known Implementation Details To Notice

- `TOKEN_SUB_DIR` is derived from `BOT_TOKEN` and is used to locate downloaded files under `BOT_API_DIR`.
- `BOT_API_DIR` and `DOWNLOAD_TO_DIR` are normalized in `src/cogs/downloader.py` to end with `/`.
- `get_file()` in `src/utils/get_file.py` retries network, timeout, and Telegram errors with exponential backoff.
- `check_file_exists()` raises if a file already exists in `DOWNLOAD_TO_DIR` or is already tracked as downloading.
- `DownloadFile` stores timing, retry, and status information for status output.
- `src/cogs/error_handler.py` sends traceback details to `env.USER_ID` and tries to reply to the affected chat/message.

## Git And Generated Files

Before editing, check current worktree state:

```bash
git status --short
```

Do not overwrite user changes. At the time this guide was created, the worktree had an existing modification in `src/cogs/downloader.py` and an untracked `codex-x86_64-pc-windows-msvc.exe`; treat such files as user-owned unless explicitly told otherwise.

Ignore generated/runtime artifacts such as:

- `__pycache__/`
- `.env`
- local download directories
- local Bot API storage directories
- large local binaries not part of the project

## Documentation Notes

The project has English and Chinese README files:

- `README.md`
- `README_CN.md`
- `README_EN.md`

If behavior changes, update the relevant README files together so setup and feature descriptions stay consistent.
