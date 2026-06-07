import asyncio
import json
import logging
import os
import shutil
import threading
import time
import urllib.error
import urllib.request
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from telegram.ext import Application

from .models import DownloadFile, downloading_files
from .utils import env
from .utils.get_file import get_file_download_progress
from .utils.runtime_settings import runtime_settings_store
from .version import get_downloader_version

logger = logging.getLogger(__name__)

_application: Application | None = None
_application_loop: asyncio.AbstractEventLoop | None = None
_server: ThreadingHTTPServer | None = None
_server_thread: threading.Thread | None = None
_last_cpu_sample: tuple[float, float] | None = None
_admin_sampler_task: asyncio.Task | None = None
_admin_refresh_until = 0.0
_admin_refresh_enabled = False
_admin_last_sample_at = 0.0
_admin_sample_count = 0
_admin_last_sample_error: str | None = None
_ADMIN_HEARTBEAT_TTL = 6.0
_ADMIN_PROGRESS_POLL_INTERVAL_DEFAULT = 0.5
_ADMIN_PROGRESS_POLL_INTERVAL_MIN = 0.2
_ADMIN_PROGRESS_POLL_INTERVAL_MAX = 10.0


def configure_application(application: Application) -> None:
    global _application
    _application = application


async def capture_application_loop(_: Application) -> None:
    global _application_loop, _admin_sampler_task
    _application_loop = asyncio.get_running_loop()
    if env.ADMIN_API_ENABLED and _admin_sampler_task is None:
        _admin_sampler_task = asyncio.create_task(_admin_progress_sampler())


def start_admin_api() -> None:
    global _server, _server_thread
    if not env.ADMIN_API_ENABLED:
        return
    if _server is not None:
        return

    address = (env.ADMIN_API_HOST, env.ADMIN_API_PORT)
    try:
        _server = ThreadingHTTPServer(address, AdminApiHandler)
    except OSError as error:
        logger.error("Failed to start Admin API on http://%s:%s: %s", *address, error)
        return
    _server_thread = threading.Thread(
        target=_server.serve_forever,
        name="admin-api",
        daemon=True,
    )
    _server_thread.start()
    logger.info("Admin API listening on http://%s:%s", *address)


def _read_text(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8") as file:
            return file.read()
    except OSError:
        return None


def _read_first_line(path: str) -> str | None:
    text = _read_text(path)
    if text is None:
        return None
    return text.splitlines()[0].strip() if text.splitlines() else None


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value.strip())
    except ValueError:
        return None


def _container_memory_limit() -> int | None:
    cgroup_v2 = _parse_int(_read_first_line("/sys/fs/cgroup/memory.max"))
    if cgroup_v2 and cgroup_v2 > 0 and cgroup_v2 < 1 << 60:
        return cgroup_v2
    cgroup_v1 = _parse_int(_read_first_line("/sys/fs/cgroup/memory/memory.limit_in_bytes"))
    if cgroup_v1 and cgroup_v1 > 0 and cgroup_v1 < 1 << 60:
        return cgroup_v1
    return None


def _clamp_admin_progress_poll_interval(value: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return _ADMIN_PROGRESS_POLL_INTERVAL_DEFAULT
    if parsed <= 0:
        return _ADMIN_PROGRESS_POLL_INTERVAL_DEFAULT
    return max(
        _ADMIN_PROGRESS_POLL_INTERVAL_MIN,
        min(parsed, _ADMIN_PROGRESS_POLL_INTERVAL_MAX),
    )


def _admin_progress_poll_interval() -> float:
    return _clamp_admin_progress_poll_interval(
        runtime_settings_store.settings.admin_progress_poll_interval
    )


def _admin_refresh_active(now: float | None = None) -> bool:
    now = now or time.monotonic()
    return _admin_refresh_enabled and now < _admin_refresh_until


def _set_admin_heartbeat(enabled: bool, ttl: float = _ADMIN_HEARTBEAT_TTL) -> dict[str, Any]:
    global _admin_refresh_enabled, _admin_refresh_until
    _admin_refresh_enabled = enabled
    _admin_refresh_until = time.monotonic() + ttl if enabled else 0.0
    return _admin_sampler_payload()


def _admin_sampler_payload() -> dict[str, Any]:
    now = time.monotonic()
    return {
        "enabled": _admin_refresh_enabled,
        "active": _admin_refresh_active(now),
        "ttl_seconds": max(0.0, round(_admin_refresh_until - now, 2)),
        "poll_interval_seconds": _admin_progress_poll_interval(),
        "last_sample_at": _admin_last_sample_at,
        "sample_count": _admin_sample_count,
        "last_error": _admin_last_sample_error,
    }


def _extract_progress_size(payload: dict[str, Any], download_file: DownloadFile) -> int | None:
    for key in ("downloaded_size", "downloaded_bytes", "local_size"):
        value = payload.get(key)
        if value is None:
            continue
        try:
            size = int(value)
        except (TypeError, ValueError):
            continue
        if download_file.file_size > 0:
            size = min(size, download_file.file_size)
        return max(0, size)
    return None


async def _sample_admin_download_progress() -> None:
    global _admin_last_sample_at, _admin_sample_count, _admin_last_sample_error
    active_files = [
        item
        for item in list(downloading_files.values())
        if item.status == "Downloading" and not item.cancel_requested
    ]
    if not active_files:
        _admin_last_sample_error = None
        return

    try:
        for download_file in active_files:
            progress = await get_file_download_progress(download_file.file_id)
            progress_size = _extract_progress_size(progress, download_file)
            if progress_size is not None:
                download_file.update_progress(progress_size)
        _admin_last_sample_at = time.time()
        _admin_sample_count += 1
        _admin_last_sample_error = None
    except Exception as error:
        _admin_last_sample_error = str(error)
        logger.debug("Admin progress sample failed: %s", error)


async def _admin_progress_sampler() -> None:
    while True:
        interval = _admin_progress_poll_interval()
        await asyncio.sleep(interval)
        if not _admin_refresh_active():
            continue
        await _sample_admin_download_progress()


def _memory_info() -> dict[str, Any]:
    meminfo = _read_text("/proc/meminfo")
    values: dict[str, int] = {}
    if meminfo:
        for line in meminfo.splitlines():
            key, _, raw_value = line.partition(":")
            parts = raw_value.strip().split()
            if parts:
                values[key] = int(parts[0]) * 1024

    limit = _container_memory_limit()
    current = _parse_int(_read_first_line("/sys/fs/cgroup/memory.current"))
    if current is None:
        current = _parse_int(_read_first_line("/sys/fs/cgroup/memory/memory.usage_in_bytes"))
    if limit and current is not None:
        total = limit
        used = current
        available = max(0, total - used)
    else:
        total = values.get("MemTotal") or 0
        available = values.get("MemAvailable") or 0
        used = max(0, total - available) if total else 0
    return {
        "total_bytes": total,
        "available_bytes": available,
        "used_bytes": used,
        "used_percent": round((used / total) * 100, 2) if total else 0,
    }


def _cpu_percent() -> float:
    global _last_cpu_sample
    stat = _read_first_line("/proc/stat")
    if not stat:
        return 0.0
    parts = stat.split()[1:]
    if len(parts) < 4:
        return 0.0
    values = [float(part) for part in parts]
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    total = sum(values)
    sample = (idle, total)
    if _last_cpu_sample is None:
        _last_cpu_sample = sample
        return 0.0
    prev_idle, prev_total = _last_cpu_sample
    _last_cpu_sample = sample
    total_delta = total - prev_total
    idle_delta = idle - prev_idle
    if total_delta <= 0:
        return 0.0
    return round(max(0.0, min(100.0, (1 - idle_delta / total_delta) * 100)), 2)


def _process_info() -> dict[str, Any]:
    status = _read_text("/proc/self/status") or ""
    values: dict[str, str] = {}
    for line in status.splitlines():
        key, _, value = line.partition(":")
        values[key] = value.strip()
    rss_kb = int(values.get("VmRSS", "0 kB").split()[0])
    return {
        "pid": os.getpid(),
        "threads": int(values.get("Threads", "0") or 0),
        "rss_bytes": rss_kb * 1024,
    }


def _disk_info(path: str) -> dict[str, Any]:
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        usage = shutil.disk_usage("/")
    used = usage.total - usage.free
    return {
        "path": path,
        "total_bytes": usage.total,
        "used_bytes": used,
        "free_bytes": usage.free,
        "used_percent": round((used / usage.total) * 100, 2) if usage.total else 0,
    }


def _bot_api_status() -> dict[str, Any]:
    url = f"{env.LOCAL_BOT_API_URL.rstrip('/')}/bot{env.BOT_TOKEN}/getMe"
    started = time.monotonic()
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return {
            "online": bool(payload.get("ok")),
            "latency_ms": round((time.monotonic() - started) * 1000),
            "url": env.LOCAL_BOT_API_URL,
        }
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as error:
        return {
            "online": False,
            "latency_ms": None,
            "url": env.LOCAL_BOT_API_URL,
            "error": str(error),
        }


def _serialize_download(file_id: str, item: DownloadFile) -> dict[str, Any]:
    progress_percent = 0.0
    if item.file_size > 0:
        progress_percent = round((item.downloaded_bytes / item.file_size) * 100, 2)
    return {
        "file_id": file_id,
        "file_name": item.file_name,
        "file_size_bytes": item.file_size,
        "downloaded_bytes": item.downloaded_bytes,
        "progress_percent": progress_percent,
        "speed_bps": round(item.download_speed_bps, 2),
        "status": item.status,
        "queued": item.queued,
        "cancel_requested": item.cancel_requested,
        "retries": item.download_retries,
        "max_retries": item.max_retries,
        "last_error": item.last_error,
        "started_at": item.start_datetime,
        "duration": item.current_download_duration,
        "eta": item.remaining_download_time,
    }


def _downloads_payload() -> dict[str, Any]:
    items = [_serialize_download(file_id, item) for file_id, item in downloading_files.items()]
    downloading = [item for item in items if item["status"] == "Downloading"]
    queued = [item for item in items if item["queued"]]
    return {
        "items": items,
        "summary": {
            "total": len(items),
            "downloading": len(downloading),
            "queued": len(queued),
            "cancelling": sum(1 for item in items if item["status"] == "Cancelling"),
        },
    }


def _run_bot_coroutine(coro) -> Any:
    if _application_loop is None:
        raise RuntimeError("telegram application loop is not ready")
    future = asyncio.run_coroutine_threadsafe(coro, _application_loop)
    return future.result(timeout=3)


def _bot_payload() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "polling": _application_loop is not None,
        "configured_user_id": env.USER_ID,
        "configured_chat_id": env.CHAT_ID,
        "bot_api": _bot_api_status(),
    }
    if _application is None:
        return payload
    try:
        bot_user = _run_bot_coroutine(_application.bot.get_me())
        payload["bot"] = bot_user.to_dict()
        payload["bot"]["online"] = True
    except Exception as error:
        payload["bot"] = {"online": False, "error": str(error)}
    return payload


def _system_payload() -> dict[str, Any]:
    settings = asdict(runtime_settings_store.settings)
    return {
        "timestamp": int(time.time()),
        "version": get_downloader_version(),
        "runtime_settings": settings,
        "resources": {
            "cpu_percent": _cpu_percent(),
            "memory": _memory_info(),
            "process": _process_info(),
            "download_disk": _disk_info(env.DOWNLOAD_TO_DIR),
            "bot_api_disk": _disk_info(env.BOT_API_DIR),
        },
        "components": {
            "downloader": {
                "online": True,
                "admin_api_enabled": env.ADMIN_API_ENABLED,
            },
            "telegram_bot_api": _bot_api_status(),
        },
        "admin_sampler": _admin_sampler_payload(),
    }


def _overview_payload() -> dict[str, Any]:
    downloads = _downloads_payload()
    system = _system_payload()
    bot = _bot_payload()
    return {
        "downloads": downloads,
        "system": system,
        "bot": bot,
    }


class AdminApiHandler(BaseHTTPRequestHandler):
    server_version = "telegram-downloader-admin-api"

    def do_OPTIONS(self) -> None:
        self._send_json({}, HTTPStatus.NO_CONTENT)

    def do_GET(self) -> None:
        if not self._authorized():
            self._send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return

        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        routes = {
            "/health": lambda: {"ok": True},
            "/api/overview": _overview_payload,
            "/api/downloads": _downloads_payload,
            "/api/system": _system_payload,
            "/api/bot": _bot_payload,
        }
        handler = routes.get(path)
        if handler is None:
            self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            self._send_json(handler())
        except Exception as error:
            logger.exception("Admin API request failed")
            self._send_json({"error": str(error)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:
        if not self._authorized():
            self._send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
            return

        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        try:
            if path == "/api/admin/heartbeat":
                payload = self._read_json_body()
                enabled = bool(payload.get("enabled", True))
                ttl = payload.get("ttl_seconds", _ADMIN_HEARTBEAT_TTL)
                try:
                    ttl = float(ttl)
                except (TypeError, ValueError):
                    ttl = _ADMIN_HEARTBEAT_TTL
                ttl = max(2.0, min(ttl, 30.0))
                self._send_json(_set_admin_heartbeat(enabled, ttl))
                return

            if path == "/api/admin/stop":
                self._send_json(_set_admin_heartbeat(False))
                return

            self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except Exception as error:
            logger.exception("Admin API POST request failed")
            self._send_json({"error": str(error)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def log_message(self, format: str, *args: Any) -> None:
        logger.debug("Admin API: " + format, *args)

    def _authorized(self) -> bool:
        if not env.ADMIN_API_TOKEN:
            return True
        token = self.headers.get("X-Admin-Token") or ""
        if token == env.ADMIN_API_TOKEN:
            return True
        auth = self.headers.get("Authorization") or ""
        return auth == f"Bearer {env.ADMIN_API_TOKEN}"

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        body = self.rfile.read(length)
        if not body:
            return {}
        payload = json.loads(body.decode("utf-8"))
        return payload if isinstance(payload, dict) else {}

    def _send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = b"" if status == HTTPStatus.NO_CONTENT else json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Admin-Token")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)
