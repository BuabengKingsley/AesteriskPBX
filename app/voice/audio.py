from dataclasses import dataclass, field


@dataclass
class AudioResult:
    audio_bytes: bytes
    content_type: str
    sample_rate: int
    encoding: str
    duration_seconds: float | None = None


@dataclass
class TranscriptResult:
    text: str
    confidence: float | None
    language: str | None
    is_final: bool
    metadata: dict = field(default_factory=dict)
