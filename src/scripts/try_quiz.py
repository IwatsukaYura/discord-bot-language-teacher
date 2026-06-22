"""ローカル動作確認用: quiz_handler を直接呼んで結果を標準出力に出す。

使い方:
    # 復習クイズ(過去調べた語を渡してテスト)
    uv run python src/scripts/try_quiz.py review "awkward" en
    uv run python src/scripts/try_quiz.py review "紅葉" ja

    # 新出クイズ(履歴を考慮せず生成、または user_id 指定で履歴反映)
    uv run python src/scripts/try_quiz.py new en
    uv run python src/scripts/try_quiz.py new ja <discord_user_id>
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio
import json
from dataclasses import asdict

from dotenv import load_dotenv

from db import quiz_log
from handlers import quiz_handler
from lib.lang import explanation_lang_for
from quiz.models import QuizContent

load_dotenv()


async def _do_review(source_word: str, target_lang: str) -> QuizContent:
    return await quiz_handler.generate_review_quiz(
        source_word=source_word,
        target_lang=target_lang,
        explanation_lang=explanation_lang_for(target_lang),
    )


async def _do_new(target_lang: str, user_id: str | None) -> QuizContent:
    history: list[str] = []
    exclusion: list[str] = []
    if user_id:
        history = quiz_log.get_recent_query_history(user_id, target_lang, limit=30)
        all_past_quiz = quiz_log.get_all_quiz_source_texts(user_id, target_lang)
        all_words = quiz_log.get_studied_target_lang_words(user_id, target_lang)
        exclusion = list(set(all_past_quiz + all_words))
    return await quiz_handler.generate_new_quiz(
        history=history,
        exclusion_list=exclusion,
        target_lang=target_lang,
        explanation_lang=explanation_lang_for(target_lang),
    )


async def main() -> None:
    if len(sys.argv) < 3:
        print(
            'Usage:\n'
            '  python src/scripts/try_quiz.py review "<word>" <en|ja>\n'
            '  python src/scripts/try_quiz.py new <en|ja> [discord_user_id]',
            file=sys.stderr,
        )
        sys.exit(1)

    mode = sys.argv[1]

    if mode == "review":
        if len(sys.argv) < 4:
            print('review requires: <word> <en|ja>', file=sys.stderr)
            sys.exit(1)
        source_word = sys.argv[2]
        target_lang = sys.argv[3]
        result = await _do_review(source_word, target_lang)
    elif mode == "new":
        target_lang = sys.argv[2]
        user_id = sys.argv[3] if len(sys.argv) > 3 else None
        result = await _do_new(target_lang, user_id)
    else:
        print(f"Unknown mode: {mode!r}. Use 'review' or 'new'.", file=sys.stderr)
        sys.exit(1)

    print()
    print("=" * 60)
    print(f"  source: {result.source_text}")
    print(f"  question: {result.question_text}")
    print("  choices:")
    for i, c in enumerate(result.choices):
        marker = " ◀ correct" if i == result.correct_index else ""
        print(f"    [{i}] {c}{marker}")
    print(f"  explanation: {result.explanation}")
    print("=" * 60)
    print()
    print(json.dumps(asdict(result), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
