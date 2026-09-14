from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.core.config import Settings, get_settings
from app.schemas.voice import TTSRequest
from app.voice.factory import get_tts_provider

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post("/tts")
async def synthesize_speech(payload: TTSRequest, settings: Annotated[Settings, Depends(get_settings)]):
    provider = get_tts_provider(settings)
    result = await provider.synthesize(payload.text, voice=payload.voice)
    return Response(content=result.audio_bytes, media_type=result.content_type,
                    headers={"X-Sample-Rate": str(result.sample_rate), "X-Encoding": result.encoding})
