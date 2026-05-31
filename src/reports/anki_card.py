"""query_log の word kind 行から Anki カード行を構築する。

query_text と result_summary は dispatcher で Mode A (順引き) / Mode B (逆引き) の
両方の形で保存されている。学習者は target_lang を Front に置きたい (例: 日本語学習者は
日本語 → 英語の方向で出題したい) ので、Mode B 行は転置して headword を Front 側へ置く。

加えて、LLM が "該当なし" / "無意味" を返したゴミ行は除外する。
"""

from dataclasses import dataclass

from lib.script import matches_target_lang

# dispatcher._summarize_headwords が " / " で結合した result_summary を分解するための区切り。
_HEADWORD_SEPARATOR = " / "

# result_summary に現れたら「LLM が意味を返せなかった」と判断する文字列。lower() 比較。
_GARBAGE_MARKERS = frozenset({"該当なし", "無意味", "no match", "n/a"})


@dataclass(frozen=True)
class AnkiCard:
    front: str  # target_lang 側 (学習者が答える側)
    back: str  # explanation_lang 側 (答え)


def _is_garbage(text: str) -> bool:
    if not text:
        return True
    stripped = text.strip()
    if not stripped:
        return True
    return stripped.lower() in {m.lower() for m in _GARBAGE_MARKERS}


def _format_front(word: str, reading: str) -> str:
    """reading があれば「単語【よみ】」形式で Front に埋め込む。"""
    if reading and reading.strip():
        return f"{word}【{reading.strip()}】"
    return word


def build_anki_cards(
    logs: list[dict],
    target_lang: str,
) -> list[AnkiCard]:
    """query_log の row 一覧から Anki カード行を構築。target_lang を常に Front 側に置く。

    Mode A (query_text が target_lang のスクリプト):
        Front = query_text (reading があれば「単語【よみ】」), Back = result_summary
    Mode B (query_text が explanation_lang のスクリプト):
        result_summary を _HEADWORD_SEPARATOR で分解し、target_lang のスクリプトに
        一致する各 headword を Front に、元の query_text を Back に。

    word kind 以外、target_lang 不一致、result_summary がゴミ (該当なし/無意味/空) の行はスキップ。
    Front が完全一致する行は最初の1件のみ採用 (出現順を保持)。
    """
    cards: list[AnkiCard] = []
    seen_fronts: set[str] = set()

    for log in logs:
        if log.get("kind") != "word":
            continue
        if log.get("target_lang") != target_lang:
            continue

        query_text = log.get("query_text") or ""
        result_summary = log.get("result_summary") or ""
        reading = log.get("reading") or ""

        if _is_garbage(result_summary):
            continue

        if matches_target_lang(query_text, target_lang):
            # Mode A: そのまま使う
            front = _format_front(query_text, reading)
            if front in seen_fronts:
                continue
            seen_fronts.add(front)
            cards.append(AnkiCard(front=front, back=result_summary))
            continue

        # Mode B: result_summary の各 headword を Front 側へ転置
        for headword in result_summary.split(_HEADWORD_SEPARATOR):
            headword = headword.strip()
            if not headword:
                continue
            if not matches_target_lang(headword, target_lang):
                continue
            # Mode B では headword 単体の reading が query_log に保存されていない
            front = _format_front(headword, "")
            if front in seen_fronts:
                continue
            seen_fronts.add(front)
            cards.append(AnkiCard(front=front, back=query_text))

    return cards
