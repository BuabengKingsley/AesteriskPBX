from app.voice.audio import AudioResult
from app.voice.tts.base import TTSProvider


class MockTTSProvider(TTSProvider):
    async def synthesize(self, text: str, voice: str | None = None) -> AudioResult:
        fake_bytes = f"MOCK-AUDIO:{voice or 'default'}:{text}".encode()
        return AudioResult(audio_bytes=fake_bytes, content_type="audio/wav", sample_rate=16000,
                           encoding="pcm_s16le", duration_seconds=round(len(text.split()) / 2.5, 2))
