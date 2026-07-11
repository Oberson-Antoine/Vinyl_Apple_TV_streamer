from datetime import datetime

from pydantic import BaseModel


class OutputInfoResponse(BaseModel):
    id: str
    name: str
    type: str
    selected: bool
    volume: int


class SetOutputsRequest(BaseModel):
    output_ids: list[str]


class SetOutputRequest(BaseModel):
    selected: bool | None = None
    volume: int | None = None


class NowPlayingResponse(BaseModel):
    title: str | None = None
    artist: str | None = None
    artwork_url: str | None = None
    recognized_at: datetime | None = None
    has_match: bool


class StatusResponse(BaseModel):
    capture_alive: bool
    current_device: str
    last_capture_chunk_at: datetime | None
    capture_dropped_chunks: int
    fifo_connected: bool
    owntone_reachable: bool
    last_recognition_attempt_at: datetime | None
    last_recognition_error: str | None


class PlaybackActionResponse(BaseModel):
    status: str


class AudioDeviceResponse(BaseModel):
    device_string: str
    description: str


class AudioDevicesListResponse(BaseModel):
    devices: list[AudioDeviceResponse]
    current_device: str


class SetAudioDeviceRequest(BaseModel):
    device: str
