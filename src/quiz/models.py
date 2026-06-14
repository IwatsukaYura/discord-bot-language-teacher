"""クイズ機能のドメインモデル。

生成結果や学習者情報を生 dict で受け渡すとキーのタイポが実行時まで検出できないため、
frozen dataclass で型と不変性を保証する。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Learner:
    """日次クイズの配信対象となる学習者。"""

    discord_user_id: str
    name: str
    target_lang: str


@dataclass(frozen=True)
class QuizContent:
    """LLM が生成した 4 択クイズ 1 問分の内容。

    reading は target_lang=ja のときだけ値が入る (それ以外は空文字)。
    example_sentence は全言語で値が入る (生成失敗時は空文字)。
    model_label は実際に応答したモデルのフッター表示用ラベル。
    """

    source_text: str
    question_text: str
    choices: tuple[str, ...]
    correct_index: int
    explanation: str
    reading: str = ""
    example_sentence: str = ""
    model_label: str | None = None
