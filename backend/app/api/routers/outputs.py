from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_state
from app.api.schemas import OutputInfoResponse, SetOutputRequest, SetOutputsRequest
from app.owntone.exceptions import OwnToneUnavailable
from app.state import AppState

router = APIRouter()


@router.get("", response_model=list[OutputInfoResponse])
async def list_outputs(state: AppState = Depends(get_state)):
    try:
        outputs = await state.owntone_client.get_outputs()
    except OwnToneUnavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return [OutputInfoResponse(**vars(o)) for o in outputs]


@router.put("", status_code=204)
async def set_outputs(body: SetOutputsRequest, state: AppState = Depends(get_state)):
    try:
        await state.owntone_client.set_outputs(body.output_ids)
    except OwnToneUnavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.put("/{output_id}", status_code=204)
async def set_output(
    output_id: str, body: SetOutputRequest, state: AppState = Depends(get_state)
):
    try:
        await state.owntone_client.set_output(
            output_id, selected=body.selected, volume=body.volume
        )
    except OwnToneUnavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
