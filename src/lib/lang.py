"""言語コード ⇔ 表示名 / 説明言語のマッピング。

「target が en なら説明は ja、target が ja なら説明は en」というペアリング知識を
ここに一元化する。プロンプト構築や日次クイズなど複数モジュールから参照される。
"""


def lang_names(target_lang: str, explanation_lang: str) -> tuple[str, str]:
    """プロンプト埋め込み用の (target_name, explanation_name) 英語表示名ペア。"""
    target_name = "English" if target_lang == "en" else "Japanese"
    explanation_name = "Japanese" if explanation_lang == "ja" else "English"
    return target_name, explanation_name


def explanation_lang_for(target_lang: str) -> str:
    """target_lang を学習する学習者の母語 (= 説明言語) を返す。"""
    return "ja" if target_lang == "en" else "en"
