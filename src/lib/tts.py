from io import BytesIO
from typing import Literal

from gtts import gTTS

SupportedLang = Literal["en", "ja"]

_SUPPORTED_LANGS: frozenset[str] = frozenset({"en", "ja"})


def synthesize_word(text: str, lang: str) -> bytes:
    """単語/短いフレーズの発音音声を mp3 バイト列で返す。

    Args:
        text: 読み上げる単語。空白のみは不可。
        lang: "en" または "ja"。

    Raises:
        ValueError: text が空・空白のみ、または lang が未対応のとき。
    """
    if not text or not text.strip():
        raise ValueError("text must not be empty or whitespace-only")
    if lang not in _SUPPORTED_LANGS:
        raise ValueError(
            f"lang must be one of {sorted(_SUPPORTED_LANGS)}, got {lang!r}"
        )

    speech = gTTS(text=text, lang=lang)
    buffer = BytesIO()
    speech.write_to_fp(buffer)
    return buffer.getvalue()
