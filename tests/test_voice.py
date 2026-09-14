import asyncio

from app.voice.stt.mock import MockSTTProvider


def test_tts_mock_endpoint_returns_audio(client):
    response = client.post("/voice/tts", json={"text": "hello"})
    assert response.status_code == 200
    assert len(response.content) > 0
    assert response.headers["content-type"] == "audio/wav"
    assert "X-Sample-Rate" in response.headers
    assert "X-Encoding" in response.headers


def test_tts_mock_endpoint_rejects_empty_text(client):
    response = client.post("/voice/tts", json={"text": ""})
    assert response.status_code == 422


def test_mock_stt_provider_returns_deterministic_transcript():
    provider = MockSTTProvider()
    result = asyncio.run(provider.transcribe(b"some-audio-bytes"))
    assert result.text == "mock transcript"
    assert result.is_final is True
    assert result.metadata["audio_bytes_received"] == len(b"some-audio-bytes")
