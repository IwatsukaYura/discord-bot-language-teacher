from reports import weekly


def _log(user: str, lang: str, kind: str, text: str, summary: str | None = "x",
         reading: str = "") -> dict:
    return {
        "kind": kind,
        "discord_user_name": user,
        "target_lang": lang,
        "query_text": text,
        "result_summary": summary,
        "reading": reading,
    }


class TestBuildWeeklySummary:
    def test_returns_empty_dict_for_empty_logs(self):
        assert weekly.build_weekly_summary([]) == {}

    def test_single_word_log_creates_nested_entry(self):
        logs = [_log("alice", "en", "word", "apple", "りんご")]
        result = weekly.build_weekly_summary(logs)
        assert result == {
            "en": {
                "word": [{"text": "apple", "summary": "りんご", "reading": "", "count": 1}]
            }
        }

    def test_aggregates_duplicate_words_with_count(self):
        logs = [
            _log("alice", "en", "word", "apple", "りんご"),
            _log("alice", "en", "word", "apple", "りんご"),
            _log("alice", "en", "word", "apple", "りんご"),
        ]
        result = weekly.build_weekly_summary(logs)
        assert result == {
            "en": {
                "word": [{"text": "apple", "summary": "りんご", "reading": "", "count": 3}]
            }
        }

    def test_merges_logs_from_different_users_for_same_target_lang(self):
        logs = [
            _log("alice", "en", "word", "apple", "りんご"),
            _log("bob", "en", "word", "banana", "バナナ"),
        ]
        result = weekly.build_weekly_summary(logs)
        assert "en" in result
        assert len(result) == 1
        words = result["en"]["word"]
        assert {w["text"] for w in words} == {"apple", "banana"}

    def test_separates_different_target_langs(self):
        logs = [
            _log("alice", "en", "word", "apple", "りんご"),
            _log("alice", "ja", "word", "林檎", "apple"),
        ]
        result = weekly.build_weekly_summary(logs)
        assert set(result.keys()) == {"en", "ja"}

    def test_merges_same_word_asked_by_different_users(self):
        logs = [
            _log("alice", "ja", "word", "視察", "inspection", reading="しさつ"),
            _log("bob", "ja", "word", "視察", "inspection", reading="しさつ"),
        ]
        result = weekly.build_weekly_summary(logs)
        item = result["ja"]["word"][0]
        assert item["text"] == "視察"
        assert item["count"] == 2

    def test_separates_different_kinds_within_same_target_lang(self):
        logs = [
            _log("alice", "en", "word", "apple", "りんご"),
            _log("alice", "en", "sentence", "Could you?", "できますか?"),
            _log("alice", "en", "grammar", "would have", "would have p.p."),
        ]
        result = weekly.build_weekly_summary(logs)
        assert set(result["en"].keys()) == {"word", "sentence", "grammar"}

    def test_sorts_items_by_count_descending(self):
        logs = [
            _log("alice", "en", "word", "apple"),
            _log("alice", "en", "word", "banana"),
            _log("alice", "en", "word", "banana"),
            _log("alice", "en", "word", "cherry"),
            _log("alice", "en", "word", "cherry"),
            _log("alice", "en", "word", "cherry"),
        ]
        result = weekly.build_weekly_summary(logs)
        words = result["en"]["word"]
        assert [w["text"] for w in words] == ["cherry", "banana", "apple"]
        assert [w["count"] for w in words] == [3, 2, 1]

    def test_preserves_first_summary_on_duplicates(self):
        logs = [
            _log("alice", "en", "word", "bank", "銀行"),
            _log("alice", "en", "word", "bank", "土手"),
        ]
        result = weekly.build_weekly_summary(logs)
        assert result["en"]["word"][0]["summary"] == "銀行"

    def test_handles_none_summary_as_empty_string(self):
        logs = [_log("alice", "en", "word", "apple", None)]
        result = weekly.build_weekly_summary(logs)
        assert result["en"]["word"][0]["summary"] == ""

    def test_preserves_reading_field_for_japanese_words(self):
        logs = [
            _log("alice", "ja", "word", "視察", "inspection", reading="しさつ"),
        ]
        result = weekly.build_weekly_summary(logs)
        assert result["ja"]["word"][0]["reading"] == "しさつ"

    def test_reading_defaults_to_empty_when_missing(self):
        logs = [
            _log("alice", "en", "word", "apple", "りんご"),
        ]
        result = weekly.build_weekly_summary(logs)
        assert result["en"]["word"][0]["reading"] == ""
