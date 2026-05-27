import discord

_QUIZ_BUTTON_PREFIX = "quiz"
_BUTTON_LABEL_MAX = 80


def _color_for(target_lang: str) -> discord.Color:
    return discord.Color.blue() if target_lang == "en" else discord.Color.red()


def _mode_label(mode: str, explanation_lang: str) -> str:
    if explanation_lang == "ja":
        return "復習" if mode == "review" else "新出"
    return "Review" if mode == "review" else "New word"


def _title_for(mode: str, explanation_lang: str, position: tuple[int, int]) -> str:
    current, total = position
    mode_label = _mode_label(mode, explanation_lang)
    if explanation_lang == "ja":
        return f"🧩 今日のクイズ ({current}/{total}) — {mode_label}"
    return f"🧩 Daily Quiz ({current}/{total}) — {mode_label}"


def _question_hint(explanation_lang: str) -> str:
    return "↓ 下のボタンから選んでね" if explanation_lang == "ja" else "↓ Tap one of the buttons below"


def build_quiz_embed(
    source_text: str,
    question_text: str,
    target_lang: str,
    explanation_lang: str,
    mode: str,
    position: tuple[int, int],
) -> discord.Embed:
    embed = discord.Embed(
        title=_title_for(mode, explanation_lang, position),
        color=_color_for(target_lang),
    )
    embed.description = f"**{source_text}**"
    embed.add_field(
        name=question_text,
        value=_question_hint(explanation_lang),
        inline=False,
    )
    return embed


def build_custom_id(quiz_id: int, choice_index: int) -> str:
    return f"{_QUIZ_BUTTON_PREFIX}:{quiz_id}:{choice_index}"


def parse_custom_id(custom_id: str) -> tuple[int, int] | None:
    """custom_id を (quiz_id, choice_index) にパース。クイズ由来でなければ None。"""
    if not custom_id.startswith(f"{_QUIZ_BUTTON_PREFIX}:"):
        return None
    parts = custom_id.split(":")
    if len(parts) != 3:
        return None
    try:
        return int(parts[1]), int(parts[2])
    except ValueError:
        return None


class QuizView(discord.ui.View):
    """4 択ボタン付き View。

    custom_id ベースで Bot 再起動を跨いで反応するため、callback は付けず
    main の on_interaction 経由で処理する。timeout=None で永続。
    """

    def __init__(self, quiz_id: int, choices: list[str]):
        super().__init__(timeout=None)
        for i, choice in enumerate(choices):
            self.add_item(
                discord.ui.Button(
                    style=discord.ButtonStyle.secondary,
                    label=choice[:_BUTTON_LABEL_MAX],
                    custom_id=build_custom_id(quiz_id, i),
                )
            )
