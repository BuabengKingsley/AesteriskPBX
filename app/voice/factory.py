from app.core.config import Settings
from app.voice.stt.base import STTProvider
from app.voice.stt.mock import MockSTTProvider
from app.voice.tts.base import TTSProvider
from app.voice.tts.mock import MockTTSProvider


def get_tts_provider(settings: Settings) -> TTSProvider:
    if settings.tts_provider == "mock":
        return MockTTSProvider()
    raise ValueError(f"Unsupported TTS provider: {settings.tts_provider}")


def get_stt_provider(settings: Settings) -> STTProvider:
    if settings.stt_provider == "mock":
        return MockSTTProvider()
    raise ValueError(f"Unsupported STT provider: {settings.stt_provider}")
