from abc import ABC, abstractmethod

from app.voice.audio import TranscriptResult


class STTProvider(ABC):
    @abstractmethod
    async def transcribe(self, audio: bytes) -> TranscriptResult:
        ...
