import discord
import pytest

from audio import playback


class TestParseCustomId:
    def test_parses_valid_english_custom_id(self):
        assert playback.parse_custom_id("tts:en:apple") == ("en", "apple")

    def test_parses_valid_japanese_custom_id(self):
        assert playback.parse_custom_id("tts:ja:視察") == ("ja", "視察")

    def test_returns_none_for_wrong_prefix(self):
        assert playback.parse_custom_id("quiz:en:apple") is None

    def test_returns_none_for_unsupported_lang(self):
        assert playback.parse_custom_id("tts:es:hola") is None

    def test_returns_none_for_empty_headword(self):
        assert playback.parse_custom_id("tts:en:") is None

    def test_returns_none_for_malformed(self):
        assert playback.parse_custom_id("tts:en") is None
        assert playback.parse_custom_id("") is None
        assert playback.parse_custom_id("random") is None

    def test_preserves_colon_inside_headword(self):
        # 万一 headword に ':' が混じってもパースが復元できる(maxsplit=2 のため)
        assert playback.parse_custom_id("tts:en:foo:bar") == ("en", "foo:bar")


class TestBuildAudioView:
    def test_returns_none_for_empty_headwords(self):
        assert playback.build_audio_view([], "en") is None

    def test_returns_none_for_unsupported_lang(self):
        assert playback.build_audio_view(["apple"], "es") is None

    def test_returns_none_for_japanese_target_lang(self):
        # 日本語学習者には単語の発音ボタンは出さない(漢字読み等で発音概念が薄いため)
        assert playback.build_audio_view(["検索", "回収"], "ja") is None

    def test_creates_one_button_per_headword(self):
        view = playback.build_audio_view(["exam", "test"], "en")

        assert view is not None
        assert len(view.children) == 2

    def test_button_label_has_speaker_emoji_and_headword(self):
        view = playback.build_audio_view(["apple"], "en")

        button = view.children[0]
        assert isinstance(button, discord.ui.Button)
        assert button.label == "apple"
        assert button.emoji is not None
        assert str(button.emoji) == "🔊"

    def test_button_custom_id_round_trips_through_parser(self):
        view = playback.build_audio_view(["exam", "test"], "en")

        parsed = [playback.parse_custom_id(b.custom_id) for b in view.children]
        assert parsed == [("en", "exam"), ("en", "test")]

    def test_caps_button_count_at_discord_action_row_limit(self):
        many = [f"word{i}" for i in range(10)]
        view = playback.build_audio_view(many, "en")

        # Discord の ActionRow は 5 ボタンまで
        assert len(view.children) == 5


class TestParseSentenceCustomId:
    def test_parses_english(self):
        assert playback.parse_sentence_custom_id("tts_sentence:en") == "en"

    def test_parses_japanese(self):
        assert playback.parse_sentence_custom_id("tts_sentence:ja") == "ja"

    def test_returns_none_for_unsupported_lang(self):
        assert playback.parse_sentence_custom_id("tts_sentence:es") is None

    def test_returns_none_for_word_custom_id(self):
        # 単語発音 custom_id と混同しない
        assert playback.parse_sentence_custom_id("tts:en:apple") is None

    def test_returns_none_for_malformed(self):
        assert playback.parse_sentence_custom_id("tts_sentence") is None
        assert playback.parse_sentence_custom_id("") is None
        assert playback.parse_sentence_custom_id("tts_sentence:") is None


class TestBuildSentenceAudioView:
    def test_creates_single_button_for_english(self):
        view = playback.build_sentence_audio_view("en")

        assert view is not None
        assert len(view.children) == 1

    def test_creates_single_button_for_japanese(self):
        # 例文音声は日本語学習者にも提供する (例文中の漢字読みを耳で確認できるように)
        view = playback.build_sentence_audio_view("ja")

        assert view is not None
        assert len(view.children) == 1

    def test_returns_none_for_unsupported_lang(self):
        assert playback.build_sentence_audio_view("es") is None

    def test_button_custom_id_round_trips(self):
        view = playback.build_sentence_audio_view("ja")

        button = view.children[0]
        assert isinstance(button, discord.ui.Button)
        assert playback.parse_sentence_custom_id(button.custom_id) == "ja"

    def test_button_has_speaker_emoji(self):
        view = playback.build_sentence_audio_view("en")

        button = view.children[0]
        assert button.emoji is not None
        assert str(button.emoji) == "🔊"


class TestExtractSentenceTextFromEmbed:
    def test_extracts_text_from_well_formed_title(self):
        embed = discord.Embed(title="📝 I went to the park.")
        assert playback.extract_sentence_text_from_embed(embed) == "I went to the park."

    def test_extracts_japanese_text(self):
        embed = discord.Embed(title="📝 昨日公園に行きました。")
        assert (
            playback.extract_sentence_text_from_embed(embed) == "昨日公園に行きました。"
        )

    def test_returns_none_when_title_missing(self):
        embed = discord.Embed()
        assert playback.extract_sentence_text_from_embed(embed) is None

    def test_returns_none_when_prefix_missing(self):
        # 例文以外の embed (📘 単語 など) を誤って読まない
        embed = discord.Embed(title="📘 apple")
        assert playback.extract_sentence_text_from_embed(embed) is None

    def test_returns_none_when_only_prefix(self):
        embed = discord.Embed(title="📝 ")
        assert playback.extract_sentence_text_from_embed(embed) is None


class TestSafeFilenameStem:
    def test_keeps_ascii_word(self):
        assert playback._safe_filename_stem("apple") == "apple"

    def test_keeps_japanese_characters(self):
        assert playback._safe_filename_stem("視察") == "視察"

    def test_replaces_punctuation_with_underscore(self):
        assert playback._safe_filename_stem("don't") == "don_t"

    def test_falls_back_to_audio_when_empty_after_sanitization(self):
        assert playback._safe_filename_stem("!!!") == "audio"
