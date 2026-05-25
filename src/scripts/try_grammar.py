"""ローカル動作確認用: grammar_handler を直接呼んで結果を標準出力に出す。

使い方:
    uv run python src/scripts/try_grammar.py "〜てしまう ってどういう意味？"
    uv run python src/scripts/try_grammar.py "What does 'would have p.p.' mean?"
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncio
import json

from dotenv import load_dotenv

from handlers import grammar_handler

load_dotenv()


async def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: python src/scripts/try_grammar.py "<question>"', file=sys.stderr)
        sys.exit(1)

    text = sys.argv[1]
    result = await grammar_handler.handle_grammar(text)

    print()
    print("=" * 60)
    print(f"  ぐりぞーひとこと: {result.get('grizzo_comment', '(なし)')}")
    print("=" * 60)
    print()
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
