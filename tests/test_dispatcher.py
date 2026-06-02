import pytest

from lib import dispatcher, tts


class TestExtractUniqueHeadwords:
    def test_returns_single_headword_for_single_sense(self):
        senses = [{"headword": "apple"}]
        assert dispatcher._extract_unique_headwords(senses) == ["apple"]

    def test_dedupes_same_headword_across_senses(self):
        senses = [{"headword": "bank"}, {"headword": "bank"}]
        assert dispatcher._extract_unique_headwords(senses) == ["bank"]

    def test_preserves_order_of_first_appearance(self):
        senses = [
            {"headword": "検索"},
            {"headword": "回収"},
            {"headword": "検索"},
        ]
        assert dispatcher._extract_unique_headwords(senses) == ["検索", "回収"]


class TestSafeFilenameStem:
    def test_keeps_ascii_word(self):
        assert dispatcher._safe_filename_stem("apple") == "apple"

    def test_keeps_japanese_characters(self):
        assert dispatcher._safe_filename_stem("視察") == "視察"

    def test_replaces_punctuation_with_underscore(self):
        assert dispatcher._safe_filename_stem("don't") == "don_t"

    def test_falls_back_to_audio_when_empty_after_sanitization(self):
        assert dispatcher._safe_filename_stem("!!!") == "audio"


class TestBuildWordAudioFiles:
    async def test_returns_one_file_per_unique_headword(self, monkeypatch):
        def fake_synth(text: str, lang: str) -> bytes:
            return f"AUDIO:{text}:{lang}".encode()

        monkeypatch.setattr(tts, "synthesize_word", fake_synth)

        senses = [{"headword": "apple"}]
        files = await dispatcher._build_word_audio_files(senses, "en")

        assert len(files) == 1
        assert files[0].filename == "apple.mp3"

    async def test_dedupes_identical_headwords_so_synthesizes_once(self, monkeypatch):
        called_with: list[str] = []

        def fake_synth(text: str, lang: str) -> bytes:
            called_with.append(text)
            return b"AUDIO"

        monkeypatch.setattr(tts, "synthesize_word", fake_synth)

        senses = [{"headword": "bank"}, {"headword": "bank"}]
        files = await dispatcher._build_word_audio_files(senses, "en")

        assert called_with == ["bank"]
        assert len(files) == 1

    async def test_skips_failed_synthesis_but_keeps_others(self, monkeypatch):
        def fake_synth(text: str, lang: str) -> bytes:
            if text == "失敗":
                raise RuntimeError("TTS failed")
            return b"AUDIO"

        monkeypatch.setattr(tts, "synthesize_word", fake_synth)

        senses = [{"headword": "視察"}, {"headword": "失敗"}]
        files = await dispatcher._build_word_audio_files(senses, "ja")

        assert len(files) == 1
        assert files[0].filename == "視察.mp3"

    async def test_japanese_headword_filename_preserved(self, monkeypatch):
        def fake_synth(text: str, lang: str) -> bytes:
            return b"AUDIO"

        monkeypatch.setattr(tts, "synthesize_word", fake_synth)

        senses = [{"headword": "検索"}, {"headword": "回収"}]
        files = await dispatcher._build_word_audio_files(senses, "ja")

        assert [f.filename for f in files] == ["検索.mp3", "回収.mp3"]
