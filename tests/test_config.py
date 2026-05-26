import pytest

import config


class TestLoadBotConfig:
    def test_en_teacher_returns_en_target_and_ja_explanation(self, monkeypatch):
        monkeypatch.setenv("BOT_ROLE", "en_teacher")
        monkeypatch.setenv("EN_LEARNER_DISCORD_ID", "111")
        monkeypatch.setenv("EN_LEARNER_NAME", "Yura")
        monkeypatch.delenv("JA_LEARNER_DISCORD_ID", raising=False)

        cfg = config.load_bot_config()

        assert cfg.role == "en_teacher"
        assert cfg.target_lang == "en"
        assert cfg.explanation_lang == "ja"
        assert cfg.learner_discord_id == "111"
        assert cfg.learner_name == "Yura"
        assert "cambridge" in cfg.dictionary_url_template.lower()

    def test_ja_teacher_returns_ja_target_and_en_explanation(self, monkeypatch):
        monkeypatch.setenv("BOT_ROLE", "ja_teacher")
        monkeypatch.setenv("JA_LEARNER_DISCORD_ID", "222")
        monkeypatch.setenv("JA_LEARNER_NAME", "Camille")

        cfg = config.load_bot_config()

        assert cfg.role == "ja_teacher"
        assert cfg.target_lang == "ja"
        assert cfg.explanation_lang == "en"
        assert cfg.learner_discord_id == "222"
        assert cfg.learner_name == "Camille"
        assert "jisho" in cfg.dictionary_url_template.lower()

    def test_learner_discord_id_is_none_when_unset(self, monkeypatch):
        monkeypatch.setenv("BOT_ROLE", "en_teacher")
        monkeypatch.delenv("EN_LEARNER_DISCORD_ID", raising=False)

        cfg = config.load_bot_config()

        assert cfg.learner_discord_id is None

    def test_default_learner_name_when_unset(self, monkeypatch):
        monkeypatch.setenv("BOT_ROLE", "ja_teacher")
        monkeypatch.delenv("JA_LEARNER_NAME", raising=False)

        cfg = config.load_bot_config()

        assert cfg.learner_name == "Japanese learner"

    def test_raises_when_bot_role_is_missing(self, monkeypatch):
        monkeypatch.delenv("BOT_ROLE", raising=False)
        with pytest.raises(RuntimeError, match="BOT_ROLE"):
            config.load_bot_config()

    def test_raises_when_bot_role_is_unknown(self, monkeypatch):
        monkeypatch.setenv("BOT_ROLE", "general_teacher")
        with pytest.raises(RuntimeError, match="BOT_ROLE"):
            config.load_bot_config()

    def test_strips_whitespace_around_bot_role(self, monkeypatch):
        monkeypatch.setenv("BOT_ROLE", "  en_teacher  ")
        cfg = config.load_bot_config()
        assert cfg.role == "en_teacher"

    def test_config_is_frozen(self, monkeypatch):
        monkeypatch.setenv("BOT_ROLE", "en_teacher")
        cfg = config.load_bot_config()
        with pytest.raises(Exception):
            cfg.target_lang = "ja"
