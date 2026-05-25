"""ローカル動作確認用: word_handler を直接呼んで結果を標準出力に出す。

使い方:
    uv run python src/scripts/try_word.py apple
    uv run python src/scripts/try_word.py りんご
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio
import json
import re

from dotenv import load_dotenv

from handlers import word_handler

load_dotenv()

_JAPANESE_PATTERN = re.compile(
    r"[぀-ゟ゠-ヿ一-鿿]"
)
_CAMBRIDGE_URL = "https://dictionary.cambridge.org/dictionary/english/{word}"
_JISHO_URL = "https://jisho.org/search/{word}"


def _contains_japanese(text: str) -> bool:
    return bool(_JAPANESE_PATTERN.search(text))


async def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python src/scripts/try_word.py <word>", file=sys.stderr)
        sys.exit(1)

    word = sys.argv[1]
    is_ja = _contains_japanese(word)
    target_lang = "ja" if is_ja else "en"
    explanation_lang = "en" if is_ja else "ja"
    url_template = _JISHO_URL if is_ja else _CAMBRIDGE_URL

    result = await word_handler.handle_word(
        word=word,
        target_lang=target_lang,
        explanation_lang=explanation_lang,
        dictionary_url_template=url_template,
    )

    print()
    print("=" * 60)
    print(f"  ぐりぞーひとこと: {result.get('grizzo_comment', '(なし)')}")
    print("=" * 60)
    print()
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
