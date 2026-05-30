from dataclasses import InitVar, dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional


@dataclass
class DownloadFile:
    file_id: str
    file_name: str
    file_size: int
    download_retries: int = 0
    max_retries: int = 3
    retry_delay: float = 2.0
    last_error: Optional[str] = None
    retry_history: List[str] = field(default_factory=list)
    cancel_requested: bool = False
    queued: bool = False
    downloaded_bytes: int = 0
    download_speed_bps: float = 0.0
    _start_datetime: InitVar[datetime] = None
    _last_progress_datetime: datetime = None
    _last_progress_bytes: int = 0
    _finish_download_datetime: datetime = None
    _finish_move_datetime: datetime = None

    def __post_init__(self, _start_datetime):
        self._start_datetime = _start_datetime or datetime.now()
        self._last_progress_datetime = self._start_datetime

    def download_complete(self):
        now = datetime.now()
        if self.file_size > 0:
            self.update_progress(self.file_size, now=now)
        self._finish_download_datetime = now

    def move_complete(self):
        self._finish_move_datetime = datetime.now()

    def request_cancel(self):
        self.cancel_requested = True

    def mark_queued(self):
        self.queued = True

    def mark_downloading(self):
        self.queued = False

    def update_progress(self, downloaded_bytes: int, now: Optional[datetime] = None) -> None:
        now = now or datetime.now()
        downloaded_bytes = max(0, int(downloaded_bytes))
        if self.file_size > 0:
            downloaded_bytes = min(downloaded_bytes, self.file_size)
        downloaded_bytes = max(downloaded_bytes, self.downloaded_bytes)

        elapsed = (now - self._last_progress_datetime).total_seconds()
        if elapsed > 0:
            delta = downloaded_bytes - self._last_progress_bytes
            self.download_speed_bps = max(0, delta) / elapsed

        self.downloaded_bytes = downloaded_bytes
        self._last_progress_bytes = downloaded_bytes
        self._last_progress_datetime = now

    @property
    def current_download_duration(self) -> str:
        duration = datetime.now() - self._start_datetime
        return self.convert_duration(duration)

    @property
    def download_duration(self) -> str:
        duration = self._finish_download_datetime - self._start_datetime
        return self.convert_duration(duration)

    @property
    def move_duration(self) -> str:
        duration = self._finish_move_datetime - self._finish_download_datetime
        return self.convert_duration(duration)

    @property
    def total_duration(self) -> str:
        duration = self._finish_move_datetime - self._start_datetime
        return self.convert_duration(duration)

    @property
    def start_datetime(self) -> str:
        return self._start_datetime.strftime("%H:%M:%S  %d/%m/%Y")

    @property
    def file_size_mb(self) -> str:
        return self.convert_size(self.file_size)

    @property
    def downloaded_size(self) -> str:
        return self.convert_transfer_size(self.downloaded_bytes)

    @property
    def download_progress(self) -> str:
        if self.file_size <= 0:
            return "0.00%"
        return f"{(self.downloaded_bytes / self.file_size) * 100:.2f}%"

    @property
    def download_speed(self) -> str:
        return self.convert_speed(self.download_speed_bps)

    @property
    def remaining_download_time(self) -> str:
        if self.file_size <= 0 or self.download_speed_bps <= 0:
            return "Unknown"
        remaining_bytes = max(0, self.file_size - self.downloaded_bytes)
        return self.convert_duration(timedelta(seconds=remaining_bytes / self.download_speed_bps))

    @property
    def status(self) -> str:
        if self._finish_move_datetime:
            return "Complete"
        if self._finish_download_datetime:
            return "Moving"
        if self.cancel_requested:
            return "Cancelling"
        if self.queued:
            return "Queued"
        return "Downloading"

    @staticmethod
    def convert_duration(time_taken: timedelta) -> str:
        total_minutes = time_taken.total_seconds() / 60
        return f"{time_taken.total_seconds():.2f} secs  ({total_minutes:.2f} mins)"

    @staticmethod
    def convert_size(size: int) -> str:
        return f"{size / 1024 / 1024:.2f} MB"

    @staticmethod
    def convert_transfer_size(size: int) -> str:
        size = max(0, int(size))
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.2f} KB"
        if size < 1024 * 1024 * 1024:
            return f"{size / 1024 / 1024:.2f} MB"
        return f"{size / 1024 / 1024 / 1024:.2f} GB"

    @classmethod
    def convert_speed(cls, bytes_per_second: float) -> str:
        if bytes_per_second <= 0:
            return "0 B/s"
        return f"{cls.convert_transfer_size(int(bytes_per_second))}/s"


# Current downloading files
downloading_files: dict[str, DownloadFile] = {}
