from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """One-time startup configuration, read from `.env` (see `.env.example`) or env
    vars. Not hot-reloaded — changing `.env` requires a process restart. Runtime state
    that should change while the app is running (selected AirPlay outputs, current
    now-playing track) belongs in `state.py` / the REST API instead, not here."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    alsa_device: str = "plughw:CARD=CODEC,DEV=0"
    sample_rate: int = 44100
    channels: int = 2
    sample_width: int = 2  # bytes per sample (S16_LE)

    capture_chunk_bytes: int = 16384
    capture_restart_backoff_seconds: list[float] = [2, 5, 10, 30]

    ring_buffer_seconds: float = 15.0
    recognize_snapshot_seconds: float = 10.0
    recognize_poll_interval_seconds: float = 25.0
    recognize_no_match_clear_threshold: int = 3

    fifo_path: str = "/var/lib/owntone/library/vinyl.pipe"
    fifo_queue_maxsize: int = 8
    fifo_reconnect_interval_seconds: float = 1.0
    fifo_reconnect_max_backoff_seconds: float = 5.0

    owntone_base_url: str = "http://localhost:3689"
    owntone_http_timeout_seconds: float = 3.0
    owntone_pipe_track_query: str = "vinyl"

    @property
    def frame_size(self) -> int:
        return self.channels * self.sample_width

    @property
    def bytes_per_second(self) -> int:
        return self.sample_rate * self.frame_size


settings = Settings()
