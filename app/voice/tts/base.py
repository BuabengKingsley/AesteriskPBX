from abc import ABC, abstractmethod

from app.voice.audio import AudioResult


class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(self, text: str, voice: str | None = None) -> AudioResult:
        ...
