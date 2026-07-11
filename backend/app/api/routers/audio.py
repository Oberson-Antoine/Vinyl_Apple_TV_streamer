from fastapi import APIRouter, Depends

from app.api.deps import get_state
from app.api.schemas import AudioDevicesListResponse, SetAudioDeviceRequest
from app.audio.devices import list_capture_devices
from app.state import AppState

router = APIRouter()


@router.get("/devices", response_model=AudioDevicesListResponse)
async def get_devices(state: AppState = Depends(get_state)):
    devices = await list_capture_devices()
    return AudioDevicesListResponse(
        devices=[{"device_string": d.device_string, "description": d.description} for d in devices],
        current_device=state.current_alsa_device,
    )


@router.post("/device", status_code=202)
async def set_device(body: SetAudioDeviceRequest, state: AppState = Depends(get_state)):
    """Switches the live capture device. Applied asynchronously by the running
    capture task (app/audio/capture.py) — this returns immediately once requested."""
    state.current_alsa_device = body.device
    state.device_change_requested.set()
