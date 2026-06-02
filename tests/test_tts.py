import pytest

from lib import tts


class _FakeGTTS:
    """gTTS のフェイク。コンストラクタ引数を記録し、write_to_fp で固定バイト列を書く。"""

    last_kwargs: dict = {}

    def __init__(self, text: str, lang: str):
        _FakeGTTS.last_kwargs = {"text": text, "lang": lang}

    def write_to_fp(self, fp) -> None:
        fp.write(b"FAKE_MP3_BYTES")


@pytest.fixture(autouse=True)
def _reset_fake_gtts():
    _FakeGTTS.last_kwargs = {}
    yield


class TestSynthesizeWord:
    def test_returns_mp3_bytes_for_english_word(self, monkeypatch):
        monkeypatch.setattr(tts, "gTTS", _FakeGTTS)

        audio = tts.synthesize_word("apple", "en")

        assert audio == b"FAKE_MP3_BYTES"

    def test_passes_text_and_lang_to_gtts_for_english(self, monkeypatch):
        monkeypatch.setattr(tts, "gTTS", _FakeGTTS)

        tts.synthesize_word("apple", "en")

        assert _FakeGTTS.last_kwargs == {"text": "apple", "lang": "en"}

    def test_passes_text_and_lang_to_gtts_for_japanese(self, monkeypatch):
        monkeypatch.setattr(tts, "gTTS", _FakeGTTS)

        tts.synthesize_word("りんご", "ja")

        assert _FakeGTTS.last_kwargs == {"text": "りんご", "lang": "ja"}

    def test_raises_on_empty_text(self, monkeypatch):
        monkeypatch.setattr(tts, "gTTS", _FakeGTTS)

        with pytest.raises(ValueError, match="text"):
            tts.synthesize_word("", "en")

    def test_raises_on_whitespace_only_text(self, monkeypatch):
        monkeypatch.setattr(tts, "gTTS", _FakeGTTS)

        with pytest.raises(ValueError, match="text"):
            tts.synthesize_word("   ", "en")

    def test_raises_on_unsupported_lang(self, monkeypatch):
        monkeypatch.setattr(tts, "gTTS", _FakeGTTS)

        with pytest.raises(ValueError, match="lang"):
            tts.synthesize_word("hola", "es")
