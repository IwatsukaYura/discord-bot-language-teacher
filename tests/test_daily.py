import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from db import query_log, quiz_log
from handlers import quiz_handler
from quiz import daily as quiz_daily
from quiz import poster
from quiz.models import Learner, QuizContent

JST = ZoneInfo("Asia/Tokyo")

_UNSET = object()


class FakeResponse:
    def __init__(self):
        self.sent = []
        self.edited = []
        self._done = False

    async def send_message(self, content=None, *, ephemeral=False, **kw):
        self.sent.append({"content": content, "ephemeral": ephemeral})
        self._done = True

    async def edit_message(self, content=_UNSET, *, view=_UNSET, **kw):
        self.edited.append({"content": content, "view": view})
        self._done = True

    def is_done(self):
        return self._done


class FakeFollowup:
    def __init__(self):
        self.sent = []

    async def send(self, content=None, *, view=None, ephemeral=False, **kw):
        self.sent.append({"content": content, "view": view, "ephemeral": ephemeral})


class FakeUser:
    def __init__(self, user_id, display_name="tester"):
        self.id = user_id
        self.display_name = display_name


class FakeInteraction:
    def __init__(self, user_id, channel="chan"):
        self.user = FakeUser(user_id)
        self.response = FakeResponse()
        self.followup = FakeFollowup()
        self.channel = channel


class FakeMessage:
    def __init__(self, message_id):
        self.id = message_id


class FakeChannel:
    def __init__(self):
        self.sent = []

    async def send(self, content=None, embed=None, view=None):
        self.sent.append({"content": content, "embed": embed, "view": view})
        return FakeMessage(len(self.sent))


def _batch_returning(n_items):
    async def fake_batch(count, history, exclusion_list, target_lang, explanation_lang):
        fake_batch.captured = {"count": count, "exclusion_list": exclusion_list}
        return [
            QuizContent(
                source_text=f"w{i}",
                question_text="?",
                choices=("a", "b", "c", "d"),
                correct_index=0,
                explanation="e",
            )
            for i in range(n_items)
        ]

    return fake_batch


def _insert_quiz_raw(db_path, user_id, target_lang, answered):
    now = datetime.now(JST).isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO quiz_log "
            "(discord_user_id, target_lang, kind, mode, source_text, question_text, "
            "choices_json, correct_index, explanation, delivered_at, answered_at) "
            "VALUES (?, ?, 'word', 'new', 's', 'q', '[]', 0, 'e', ?, ?)",
            (user_id, target_lang, now, now if answered else None),
        )


@pytest.fixture
def db_path(tmp_path):
    p = tmp_path / "test.db"
    query_log.init_db(p)
    quiz_log.init_db(p)
    return p


class TestHandleAddonRequest:
    async def test_rejects_when_not_the_owner(self, db_path):
        interaction = FakeInteraction(user_id=999)

        await quiz_daily.handle_addon_request(
            interaction, user_id="111", target_lang="en", count=2, db_path=db_path,
        )

        assert interaction.response.sent[0]["ephemeral"] is True
        assert quiz_log.has_used_addon_today("111", "en", db_path=db_path) is False

    async def test_decline_consumes_allowance_without_posting(self, db_path, monkeypatch):
        posted = []

        async def fake_post(channel, learner, count, db_path=None):
            posted.append(count)

        monkeypatch.setattr(quiz_daily, "post_addon_quizzes", fake_post)
        interaction = FakeInteraction(user_id=111)

        await quiz_daily.handle_addon_request(
            interaction, user_id="111", target_lang="en", count=0, db_path=db_path,
        )

        assert quiz_log.has_used_addon_today("111", "en", db_path=db_path) is True
        assert posted == []
        assert interaction.response.edited[0]["view"] is None

    async def test_accept_marks_used_and_posts(self, db_path, monkeypatch):
        posted = []

        async def fake_post(channel, learner, count, db_path=None):
            posted.append((learner.discord_user_id, count))

        monkeypatch.setattr(quiz_daily, "post_addon_quizzes", fake_post)
        interaction = FakeInteraction(user_id=111)

        await quiz_daily.handle_addon_request(
            interaction, user_id="111", target_lang="en", count=3, db_path=db_path,
        )

        assert quiz_log.has_used_addon_today("111", "en", db_path=db_path) is True
        assert posted == [("111", 3)]

    async def test_already_used_does_not_post(self, db_path, monkeypatch):
        posted = []

        async def fake_post(channel, learner, count, db_path=None):
            posted.append(count)

        monkeypatch.setattr(quiz_daily, "post_addon_quizzes", fake_post)
        quiz_log.mark_addon_used("111", "en", db_path=db_path)
        interaction = FakeInteraction(user_id=111)

        await quiz_daily.handle_addon_request(
            interaction, user_id="111", target_lang="en", count=2, db_path=db_path,
        )

        assert posted == []


class TestPostAddonQuizzes:
    async def test_posts_each_generated_quiz(self, db_path, monkeypatch):
        fake_batch = _batch_returning(3)
        monkeypatch.setattr(quiz_handler, "generate_new_quiz_batch", fake_batch)
        channel = FakeChannel()
        learner = Learner(discord_user_id="111", name="t", target_lang="en")

        await quiz_daily.post_addon_quizzes(channel, learner, count=3, db_path=db_path)

        assert len(channel.sent) == 3
        with sqlite3.connect(db_path) as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM quiz_log WHERE discord_user_id='111'"
            ).fetchone()[0]
        assert n == 3
        assert fake_batch.captured["count"] == 3

    async def test_posts_only_what_batch_returns(self, db_path, monkeypatch):
        fake_batch = _batch_returning(1)
        monkeypatch.setattr(quiz_handler, "generate_new_quiz_batch", fake_batch)
        channel = FakeChannel()
        learner = Learner(discord_user_id="111", name="t", target_lang="en")

        await quiz_daily.post_addon_quizzes(channel, learner, count=3, db_path=db_path)

        assert len(channel.sent) == 1


class TestMaybeOfferAddon:
    async def test_offers_when_all_answered_and_unused(self, db_path):
        _insert_quiz_raw(db_path, "111", "en", answered=True)
        interaction = FakeInteraction(user_id=111)

        await quiz_daily._maybe_offer_addon(
            interaction, "111", "en", "ja", db_path,
        )

        assert len(interaction.followup.sent) == 1
        assert isinstance(interaction.followup.sent[0]["view"], poster.AddonView)

    async def test_no_offer_when_quizzes_remain(self, db_path):
        _insert_quiz_raw(db_path, "111", "en", answered=False)
        interaction = FakeInteraction(user_id=111)

        await quiz_daily._maybe_offer_addon(
            interaction, "111", "en", "ja", db_path,
        )

        assert interaction.followup.sent == []

    async def test_no_offer_when_already_used(self, db_path):
        _insert_quiz_raw(db_path, "111", "en", answered=True)
        quiz_log.mark_addon_used("111", "en", db_path=db_path)
        interaction = FakeInteraction(user_id=111)

        await quiz_daily._maybe_offer_addon(
            interaction, "111", "en", "ja", db_path,
        )

        assert interaction.followup.sent == []
