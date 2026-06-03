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


class TestParseWordExampleCustomId:
    def test_parses_valid(self):
        assert playback.parse_word_example_custom_id("tts_ex:en:0:2") == ("en", 0, 2)

    def test_parses_japanese(self):
        assert playback.parse_word_example_custom_id("tts_ex:ja:1:0") == ("ja", 1, 0)

    def test_returns_none_for_word_custom_id(self):
        # 単語発音 (tts:lang:headword) と混同しない
        assert playback.parse_word_example_custom_id("tts:en:apple") is None

    def test_returns_none_for_unsupported_lang(self):
        assert playback.parse_word_example_custom_id("tts_ex:es:0:0") is None

    def test_returns_none_for_non_integer_index(self):
        assert playback.parse_word_example_custom_id("tts_ex:en:a:0") is None
        assert playback.parse_word_example_custom_id("tts_ex:en:0:b") is None

    def test_returns_none_for_negative_index(self):
        assert playback.parse_word_example_custom_id("tts_ex:en:-1:0") is None

    def test_returns_none_for_malformed(self):
        assert playback.parse_word_example_custom_id("tts_ex:en:0") is None
        assert playback.parse_word_example_custom_id("tts_ex") is None
        assert playback.parse_word_example_custom_id("") is None


class TestExampleButtonLabel:
    def test_single_sense_uses_example_label(self):
        # 単一 sense なら sense番号は出さず "例文1", "例文2" のみ
        assert playback._example_button_label(0, 0, multi_sense=False) == "例文1"
        assert playback._example_button_label(0, 1, multi_sense=False) == "例文2"

    def test_multi_sense_uses_hierarchical_label(self):
        # 複数 sense なら "1-1", "1-2", "2-1" 形式 (1-indexed で表示)
        assert playback._example_button_label(0, 0, multi_sense=True) == "1-1"
        assert playback._example_button_label(0, 1, multi_sense=True) == "1-2"
        assert playback._example_button_label(1, 0, multi_sense=True) == "2-1"


class TestBuildWordAudioView:
    def _make_sense(self, headword: str, n_examples: int) -> dict:
        return {
            "headword": headword,
            "examples": [
                {"source": f"sentence {i}", "translation": f"訳 {i}"}
                for i in range(n_examples)
            ],
        }

    def test_returns_none_for_empty_senses(self):
        assert playback.build_word_audio_view([], [], "en") is None

    def test_returns_none_for_unsupported_lang(self):
        senses = [self._make_sense("apple", 1)]
        assert playback.build_word_audio_view(["apple"], senses, "es") is None

    def test_returns_none_when_no_buttons_to_add(self):
        # ja + examples 空 → 発音もボタンもなし
        senses = [self._make_sense("検索", 0)]
        assert playback.build_word_audio_view(["検索"], senses, "ja") is None

    def test_english_single_sense_includes_pronunciation_and_examples(self):
        senses = [self._make_sense("apple", 2)]
        view = playback.build_word_audio_view(["apple"], senses, "en")

        assert view is not None
        # 発音(apple) 1 + 例文 2 = 3
        assert len(view.children) == 3

    def test_japanese_omits_pronunciation_but_includes_examples(self):
        senses = [self._make_sense("検索", 2)]
        view = playback.build_word_audio_view(["検索"], senses, "ja")

        assert view is not None
        # ja は発音なし、例文 2 のみ
        assert len(view.children) == 2

    def test_example_button_custom_ids_round_trip(self):
        senses = [
            self._make_sense("試験", 2),
            self._make_sense("実験", 1),
        ]
        view = playback.build_word_audio_view(["試験", "実験"], senses, "ja")

        assert view is not None
        custom_ids = [b.custom_id for b in view.children]
        parsed = [playback.parse_word_example_custom_id(c) for c in custom_ids]
        assert parsed == [("ja", 0, 0), ("ja", 0, 1), ("ja", 1, 0)]

    def test_multi_sense_labels_are_hierarchical(self):
        senses = [self._make_sense("試験", 1), self._make_sense("実験", 1)]
        view = playback.build_word_audio_view(["試験", "実験"], senses, "ja")

        labels = [b.label for b in view.children]
        assert labels == ["1-1", "2-1"]

    def test_single_sense_labels_are_flat(self):
        senses = [self._make_sense("apple", 2)]
        view = playback.build_word_audio_view(["apple"], senses, "en")

        # 発音ボタンの label = "apple"、例文ボタン = "例文1", "例文2"
        labels = [b.label for b in view.children]
        assert labels == ["apple", "例文1", "例文2"]


class TestExtractWordExampleTextFromEmbed:
    def _make_embed_with_field(self, value: str) -> discord.Embed:
        embed = discord.Embed(title="📘 test")
        embed.add_field(name="sense", value=value, inline=False)
        return embed

    def test_extracts_first_example_from_single_sense(self):
        # build_word_embed が組む実フォーマットを模倣 (translations行 + 空行 + 例文)
        value = (
            "**Translation**: 試験 / テスト\n"
            "\n"
            "1. I have a math test tomorrow.\n"
            "    → 明日数学のテストがある。\n"
            "2. He is studying hard for his test.\n"
            "    → 彼はテストのために勉強している。"
        )
        embed = self._make_embed_with_field(value)

        assert (
            playback.extract_word_example_text_from_embed(embed, 0, 0)
            == "I have a math test tomorrow."
        )
        assert (
            playback.extract_word_example_text_from_embed(embed, 0, 1)
            == "He is studying hard for his test."
        )

    def test_extracts_from_japanese_sense(self):
        value = (
            "**訳**: test / exam\n"
            "\n"
            "1. 明日は数学の試験がある。\n"
            "    → I have a math test tomorrow.\n"
            "2. 彼は試験のために一生懸命勉強している。\n"
            "    → He is studying hard for his test."
        )
        embed = self._make_embed_with_field(value)

        assert (
            playback.extract_word_example_text_from_embed(embed, 0, 1)
            == "彼は試験のために一生懸命勉強している。"
        )

    def test_returns_none_for_out_of_range_sense_idx(self):
        embed = self._make_embed_with_field("1. foo\n    → bar")
        assert playback.extract_word_example_text_from_embed(embed, 5, 0) is None

    def test_returns_none_for_out_of_range_example_idx(self):
        embed = self._make_embed_with_field("1. foo\n    → bar")
        assert playback.extract_word_example_text_from_embed(embed, 0, 5) is None

    def test_returns_none_when_field_has_no_examples(self):
        # translations のみで例文がない field
        embed = self._make_embed_with_field("**Translation**: foo / bar")
        assert playback.extract_word_example_text_from_embed(embed, 0, 0) is None

    def test_handles_multi_sense_embed(self):
        embed = discord.Embed(title="📘 test")
        embed.add_field(
            name="【1】 試験",
            value="1. 明日は試験がある。\n    → I have a test tomorrow.",
            inline=False,
        )
        embed.add_field(
            name="【2】 実験",
            value="1. 科学者は実験を行った。\n    → The scientist conducted an experiment.",
            inline=False,
        )

        assert (
            playback.extract_word_example_text_from_embed(embed, 1, 0)
            == "科学者は実験を行った。"
        )


class TestSafeFilenameStem:
    def test_keeps_ascii_word(self):
        assert playback._safe_filename_stem("apple") == "apple"

    def test_keeps_japanese_characters(self):
        assert playback._safe_filename_stem("視察") == "視察"

    def test_replaces_punctuation_with_underscore(self):
        assert playback._safe_filename_stem("don't") == "don_t"

    def test_falls_back_to_audio_when_empty_after_sanitization(self):
        assert playback._safe_filename_stem("!!!") == "audio"
