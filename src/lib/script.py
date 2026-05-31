"""文字種(スクリプト)で言語を判定するヘルパー。

クイズ生成で「target_lang のスクリプトで書かれた語」だけを扱うために使う。
日本語学習者のチャンネルに英語の単語が混入してクイズに出るのを防ぐ目的。
"""

_HIRAGANA_RANGE = (0x3040, 0x309F)
_KATAKANA_RANGE = (0x30A0, 0x30FF)
_CJK_UNIFIED_RANGE = (0x4E00, 0x9FFF)


def _has_japanese_char(text: str) -> bool:
    for ch in text:
        code = ord(ch)
        if _HIRAGANA_RANGE[0] <= code <= _HIRAGANA_RANGE[1]:
            return True
        if _KATAKANA_RANGE[0] <= code <= _KATAKANA_RANGE[1]:
            return True
        if _CJK_UNIFIED_RANGE[0] <= code <= _CJK_UNIFIED_RANGE[1]:
            return True
    return False


def _has_ascii_letter(text: str) -> bool:
    return any(ch.isascii() and ch.isalpha() for ch in text)


def matches_target_lang(text: str, target_lang: str) -> bool:
    """text が target_lang のスクリプトで書かれているか判定。

    ja: ひらがな/カタカナ/CJK統合漢字 を1文字以上含む
    en: 日本語文字を一切含まず、ASCIIレターを1文字以上含む

    空文字列・空白のみ・記号のみは False。未知の target_lang も False。
    """
    if not text:
        return False
    stripped = text.strip()
    if not stripped:
        return False
    if target_lang == "ja":
        return _has_japanese_char(stripped)
    if target_lang == "en":
        return not _has_japanese_char(stripped) and _has_ascii_letter(stripped)
    return False
