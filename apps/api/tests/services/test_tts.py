from unittest.mock import patch

from app.services.tts import GeminiEngine, synthesize

FAKE_AUDIO = b"\xff\xfb\x90\x00"


def test_synthesize_returns_empty_when_no_provider_configured() -> None:
    with patch("app.services.tts.get_settings") as mock_settings:
        mock_settings.return_value.voice_agent_provider = ""
        result = synthesize("hello")
    assert result == ""


def test_synthesize_returns_empty_on_empty_text() -> None:
    with patch("app.services.tts.get_settings") as mock_settings:
        mock_settings.return_value.voice_agent_provider = "gemini"
        result = synthesize("  ")
    assert result == ""


def test_synthesize_calls_engine_and_returns_url() -> None:
    audio_url = "https://r2.example.com/audio/test.mp3"
    with (
        patch("app.services.tts.get_settings") as mock_settings,
        patch.object(GeminiEngine, "synthesize", return_value=FAKE_AUDIO) as mock_synth,
        patch("app.services.tts._upload_to_r2", return_value=audio_url) as mock_upload,
    ):
        mock_settings.return_value.voice_agent_provider = "gemini"
        mock_settings.return_value.voice_agent_voice = "en-US-Standard-H"
        result = synthesize("hello")
    assert result == audio_url
    mock_synth.assert_called_once_with("hello", "en-US-Standard-H")
    mock_upload.assert_called_once()


def test_synthesize_returns_empty_on_exhausted_retries() -> None:
    with (
        patch("app.services.tts.get_settings") as mock_settings,
        patch.object(GeminiEngine, "synthesize", side_effect=RuntimeError("boom")),
        patch("app.services.tts._upload_to_r2") as mock_upload,
    ):
        mock_settings.return_value.voice_agent_provider = "gemini"
        result = synthesize("hello")
    assert result == ""
    mock_upload.assert_not_called()
