from lib import embeds


def _word_result(**extra):
    base = {
        "input": "apple",
        "senses": [{"headword": "apple", "translations": ["りんご"]}],
        "dictionary_url": "http://x",
    }
    base.update(extra)
    return base


def _sentence_result(**extra):
    base = {
        "source_text": "I am here.",
        "translation": "私はここにいる。",
        "literal_translation": "",
        "key_points": [],
    }
    base.update(extra)
    return base


def _grammar_result(**extra):
    base = {
        "topic": "〜てしまう",
        "target_lang": "ja",
        "explanation_lang": "en",
        "explanation": "expresses completion",
        "examples": [],
        "related": "",
    }
    base.update(extra)
    return base


class TestWordEmbedFooter:
    def test_shows_model_footer_when_present(self):
        embed = embeds.build_word_embed(
            _word_result(model_label="gemini-3.1-flash-lite"), "en", "ja",
        )
        assert embed.footer.text == "via gemini-3.1-flash-lite"

    def test_no_footer_when_absent(self):
        embed = embeds.build_word_embed(_word_result(), "en", "ja")
        assert embed.footer.text is None


class TestSentenceEmbedFooter:
    def test_shows_model_footer_when_present(self):
        embed = embeds.build_sentence_embed(
            _sentence_result(model_label="openrouter · vendor/model"), "ja", "en",
        )
        assert embed.footer.text == "via openrouter · vendor/model"


class TestGrammarEmbedFooter:
    def test_shows_model_footer_when_present(self):
        embed = embeds.build_grammar_embed(
            _grammar_result(model_label="gemini-3.1-flash"),
        )
        assert embed.footer.text == "via gemini-3.1-flash"
