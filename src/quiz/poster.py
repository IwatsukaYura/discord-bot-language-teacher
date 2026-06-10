from collections.abc import Sequence

import discord

_QUIZ_BUTTON_PREFIX = "quiz"
_ADDON_BUTTON_PREFIX = "quizadd"
_ADDON_COUNTS = (1, 2, 3)
_ADDON_DECLINE = 0
_BUTTON_LABEL_MAX = 80


def _color_for(target_lang: str) -> discord.Color:
    return discord.Color.blue() if target_lang == "en" else discord.Color.red()


def _mode_label(mode: str, explanation_lang: str) -> str:
    if explanation_lang == "ja":
        return "復習" if mode == "review" else "新出"
    return "Review" if mode == "review" else "New word"


def _title_for(
    mode: str,
    explanation_lang: str,
    position: tuple[int, int],
    addon: bool = False,
) -> str:
    current, total = position
    mode_label = _mode_label(mode, explanation_lang)
    if explanation_lang == "ja":
        prefix = "追加クイズ" if addon else "今日のクイズ"
        return f"🧩 {prefix} ({current}/{total}) — {mode_label}"
    prefix = "Bonus Quiz" if addon else "Daily Quiz"
    return f"🧩 {prefix} ({current}/{total}) — {mode_label}"


def _question_hint(explanation_lang: str) -> str:
    return "↓ 下のボタンから選んでね" if explanation_lang == "ja" else "↓ Tap one of the buttons below"


def _build_description(
    source_text: str,
    reading: str | None,
    example: str | None,
    explanation_lang: str,
) -> str:
    """source_text 行(必要なら読み仮名併記) + 例文行 を組み立てる。

    reading は source_text と異なる、かつ非空のときだけ括弧書きで併記する
    (LLM が仮名のみ語に reading を返してきた場合のフォールバック)。
    example は非空なら 📖 例文: 形式で追記する。
    """
    head = f"**{source_text}**"
    if reading and reading != source_text:
        head = f"{head}（{reading}）"

    if not example:
        return head

    example_label = "例文" if explanation_lang == "ja" else "Example"
    return f"{head}\n📖 {example_label}: {example}"


def build_quiz_embed(
    source_text: str,
    question_text: str,
    target_lang: str,
    explanation_lang: str,
    mode: str,
    position: tuple[int, int],
    addon: bool = False,
    model_label: str | None = None,
    reading: str | None = None,
    example: str | None = None,
) -> discord.Embed:
    embed = discord.Embed(
        title=_title_for(mode, explanation_lang, position, addon=addon),
        color=_color_for(target_lang),
    )
    embed.description = _build_description(source_text, reading, example, explanation_lang)
    embed.add_field(
        name=question_text,
        value=_question_hint(explanation_lang),
        inline=False,
    )
    if model_label:
        embed.set_footer(text=f"via {model_label}")
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

    def __init__(self, quiz_id: int, choices: Sequence[str]):
        super().__init__(timeout=None)
        for i, choice in enumerate(choices):
            self.add_item(
                discord.ui.Button(
                    style=discord.ButtonStyle.secondary,
                    label=choice[:_BUTTON_LABEL_MAX],
                    custom_id=build_custom_id(quiz_id, i),
                )
            )


def build_addon_custom_id(user_id: str, target_lang: str, count: int) -> str:
    return f"{_ADDON_BUTTON_PREFIX}:{user_id}:{target_lang}:{count}"


def parse_addon_custom_id(custom_id: str) -> tuple[str, str, int] | None:
    """追加クイズボタンの custom_id を (user_id, target_lang, count) にパース。

    自分以外由来 / 不正形式なら None。count は 0(なし)〜3 のみ許可。
    """
    if not custom_id.startswith(f"{_ADDON_BUTTON_PREFIX}:"):
        return None
    parts = custom_id.split(":")
    if len(parts) != 4:
        return None
    user_id, target_lang, count_str = parts[1], parts[2], parts[3]
    try:
        count = int(count_str)
    except ValueError:
        return None
    if count not in (_ADDON_DECLINE, *_ADDON_COUNTS):
        return None
    return user_id, target_lang, count


def build_addon_prompt(explanation_lang: str) -> str:
    if explanation_lang == "ja":
        return "🔥 もっとやる? 追加できるのは今日ここまで。下から選んでね"
    return "🔥 Want more? This is your one chance today — pick below"


class AddonView(discord.ui.View):
    """追加クイズの増減を選ぶ View (+1 / +2 / +3 / なし)。

    QuizView と同様 custom_id ベースで永続化し、main の on_interaction で処理する。
    custom_id に user_id と target_lang を埋め込み、本人検証と言語特定を自己完結させる。
    """

    def __init__(self, user_id: str, target_lang: str, explanation_lang: str):
        super().__init__(timeout=None)
        for count in _ADDON_COUNTS:
            self.add_item(
                discord.ui.Button(
                    style=discord.ButtonStyle.primary,
                    label=f"+{count}",
                    custom_id=build_addon_custom_id(user_id, target_lang, count),
                )
            )
        decline_label = "なし" if explanation_lang == "ja" else "No thanks"
        self.add_item(
            discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label=decline_label,
                custom_id=build_addon_custom_id(user_id, target_lang, _ADDON_DECLINE),
            )
        )
