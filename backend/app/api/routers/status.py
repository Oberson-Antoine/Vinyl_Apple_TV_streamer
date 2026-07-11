from fastapi import APIRouter, Depends

from app.api.deps import get_state
from app.api.schemas import NowPlayingResponse, StatusResponse
from app.state import AppState

router = APIRouter()


@router.get("/now-playing", response_model=NowPlayingResponse)
async def now_playing(state: AppState = Depends(get_state)):
    track = state.now_playing
    if track is None:
        return NowPlayingResponse(has_match=False)
    return NowPlayingResponse(
        title=track.title,
        artist=track.artist,
        artwork_url=track.artwork_url,
        recognized_at=track.recognized_at,
        has_match=True,
    )


@router.get("/status", response_model=StatusResponse)
async def status(state: AppState = Depends(get_state)):
    return StatusResponse(
        capture_alive=state.capture_alive,
        last_capture_chunk_at=state.last_capture_chunk_at,
        capture_dropped_chunks=state.capture_dropped_chunks,
        fifo_connected=state.fifo_connected,
        owntone_reachable=await state.owntone_client.health(),
        last_recognition_attempt_at=state.last_recognition_attempt_at,
        last_recognition_error=state.last_recognition_error,
    )
