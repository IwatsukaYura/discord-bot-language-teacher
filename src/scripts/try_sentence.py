"""ローカル動作確認用: sentence_handler を直接呼んで結果を標準出力に出す。

使い方:
    uv run python src/scripts/try_sentence.py "She ate a red apple."
    uv run python src/scripts/try_sentence.py "今日は雨が降りそうだ。"
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio
import json
import re

from dotenv import load_dotenv

from handlers import sentence_handler

load_dotenv()

_JAPANESE_PATTERN = re.compile(r"[぀-ゟ゠-ヿ一-鿿]")


def _contains_japanese(text: str) -> bool:
    return bool(_JAPANESE_PATTERN.search(text))


async def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: python src/scripts/try_sentence.py "<sentence>"', file=sys.stderr)
        sys.exit(1)

    text = sys.argv[1]
    is_ja = _contains_japanese(text)
    target_lang = "ja" if is_ja else "en"
    explanation_lang = "en" if is_ja else "ja"

    result = await sentence_handler.handle_sentence(
        text=text,
        target_lang=target_lang,
        explanation_lang=explanation_lang,
    )

    print()
    print("=" * 60)
    print(f"  ぐりぞーひとこと: {result.get('grizzo_comment', '(なし)')}")
    print("=" * 60)
    print()
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
