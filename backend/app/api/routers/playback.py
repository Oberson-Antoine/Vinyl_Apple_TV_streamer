from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_state
from app.api.schemas import PlaybackActionResponse
from app.config import settings
from app.owntone.exceptions import OwnToneUnavailable
from app.state import AppState

router = APIRouter()


@router.post("/start", response_model=PlaybackActionResponse)
async def start_playback(state: AppState = Depends(get_state)):
    try:
        await state.owntone_client.start_pipe_playback(settings.owntone_pipe_track_query)
    except OwnToneUnavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return PlaybackActionResponse(status="started")


@router.post("/stop", response_model=PlaybackActionResponse)
async def stop_playback(state: AppState = Depends(get_state)):
    try:
        await state.owntone_client.stop_playback()
    except OwnToneUnavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return PlaybackActionResponse(status="stopped")
