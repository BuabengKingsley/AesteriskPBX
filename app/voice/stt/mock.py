from app.voice.audio import TranscriptResult
from app.voice.stt.base import STTProvider


class MockSTTProvider(STTProvider):
    async def transcribe(self, audio: bytes) -> TranscriptResult:
        return TranscriptResult(text="mock transcript", confidence=1.0, language="en-GH", is_final=True,
                                metadata={"audio_bytes_received": len(audio)})
