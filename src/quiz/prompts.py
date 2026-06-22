"""クイズ生成用プロンプトの構築。

handlers.quiz_handler から分離したプロンプト専用モジュール。
LLM 呼び出しやパースは行わず、文字列を組み立てる責務だけを持つ。
"""

from lib.lang import lang_names

_LEVEL_HINT = {
    "ja": (
        "Target JLPT N3 to N2 vocabulary (intermediate to upper-intermediate). "
        "Do NOT exceed N2 difficulty. "
        "Idioms (慣用句), proverbs, and colloquial expressions are welcome — "
        "BUT prefer ones commonly used in daily Japanese conversation; "
        "avoid rare, literary, archaic, or highly technical expressions."
    ),
    "en": (
        "Target Eiken Pre-1 to IELTS 7.0 vocabulary (upper-intermediate to advanced). "
        "Idioms and colloquial expressions are welcome — "
        "BUT prefer ones commonly used in daily English conversation; "
        "avoid rare, literary, archaic, or highly technical expressions."
    ),
}


def _level_hint(target_lang: str) -> str:
    return _LEVEL_HINT.get(
        target_lang,
        "Target a common, intermediate-level vocabulary item used in daily conversation.",
    )


_EXAMPLE_MAX_CHARS = {"ja": 60, "en": 100}
_DEFAULT_EXAMPLE_MAX_CHARS = 80


def _example_max_chars(target_lang: str) -> int:
    return _EXAMPLE_MAX_CHARS.get(target_lang, _DEFAULT_EXAMPLE_MAX_CHARS)


def _extra_fields_schema(target_lang: str, target_name: str) -> str:
    """出題に追加するフィールドの JSON スキーマ片。

    example_sentence は全言語共通。reading は ja(漢字の読み)のみ追加する。
    先頭は既存フィールドへ続けるためのカンマ + 改行で始める。
    """
    max_chars = _example_max_chars(target_lang)
    fields: list[str] = []
    if target_lang == "ja":
        fields.append(
            '  "reading": "hiragana reading of source_text — REQUIRED when source_text '
            "contains any kanji (CJK Unified Ideographs); EMPTY STRING when source_text "
            'is kana-only. Do NOT include the word itself, just the reading."'
        )
    fields.append(
        f'  "example_sentence": "ONE short natural {target_name} sentence (under '
        f"{max_chars} chars) that uses source_text in context. Plain {target_name} "
        'only, no translation, no annotations."'
    )
    return ",\n" + ",\n".join(fields)


def _extra_fields_rules(target_lang: str, target_name: str) -> str:
    """example_sentence / reading に関する追加ルール文。

    example_sentence は全言語共通。reading は ja のみ。
    """
    max_chars = _example_max_chars(target_lang)
    rules: list[str] = []
    if target_lang == "ja":
        rules.append(
            "reading: when source_text contains any kanji, provide the full hiragana "
            "reading; when source_text is fully kana, return an empty string. "
            "NEVER include English or romaji."
        )
    rules.append(
        f"example_sentence: a natural daily-conversation {target_name} sentence that "
        "uses source_text. Must contain source_text as-is (do not change the surface "
        f"form). Do not translate the sentence; keep it under {max_chars} characters."
    )
    return "\n- " + "\n- ".join(rules)


def _history_section(history: list[str]) -> str:
    if history:
        return (
            "Learner's recent study history (for topical context only — NOT a level guide):\n"
            + ", ".join(history)
        )
    return "Learner has no study history yet."


def _exclusion_section(exclusion_list: list[str]) -> str:
    if exclusion_list:
        return (
            "FORBIDDEN WORDS — these were already studied or quizzed. "
            "You MUST NOT pick any of them. Picking any one is an invalid response:\n"
            + ", ".join(exclusion_list)
        )
    return "No exclusions."


def build_review_prompt(target_lang: str, explanation_lang: str) -> str:
    """過去に学習した語の復習クイズ用 system prompt。"""
    target_name, explanation_name = lang_names(target_lang, explanation_lang)
    extra_schema = _extra_fields_schema(target_lang, target_name)
    extra_rules = _extra_fields_rules(target_lang, target_name)
    return f"""You are a {target_name} language quiz creator for {explanation_name} speakers.

The learner studied a {target_name} word in the past and the word will be provided as the user message. Create a 4-option multiple-choice quiz testing whether they recall its meaning.

Return a JSON object with this exact structure:

{{
  "question_text": "a question in {explanation_name} that QUOTES the source word by name and asks for its meaning. Substitute <WORD> with the actual source word. Template: \\"「<WORD>」の意味として最も適切なものはどれですか？\\" (when {explanation_name} is Japanese) or \\"What does <WORD> mean?\\" (when English)",
  "choices": ["choice 1", "choice 2", "choice 3", "choice 4"],
  "correct_index": <int 0-3 indicating which choice is correct>,
  "explanation": "brief explanation in {explanation_name} (under 200 chars)"{extra_schema}
}}

Rules:
- The question_text MUST quote the source word by name and ask for its meaning. NEVER phrase it as "which word means X" or any reverse direction; the source word is shown in the embed description, so the reverse direction would reveal the answer.
- All 4 choices are meanings in {explanation_name}. NEVER include a {target_name} word as a choice.
- Distractors should be confusable (similar category, similar level) but clearly wrong.
- Keep each choice short (under 30 characters where possible, hard max 80 for Discord button label).
- Randomize the correct answer's position (do not always put it at index 0).
- Explanation should be neutral reference-book tone (no character voice, no 〜だよ / 〜だね).{extra_rules}

Respond ONLY with the JSON object, no markdown fences, no extra text."""


def build_new_prompt(
    target_lang: str,
    explanation_lang: str,
    history: list[str],
    exclusion_list: list[str],
) -> str:
    """未学習語 1 つの新出クイズ用 system prompt。"""
    target_name, explanation_name = lang_names(target_lang, explanation_lang)
    extra_schema = _extra_fields_schema(target_lang, target_name)
    extra_rules = _extra_fields_rules(target_lang, target_name)
    return f"""You are a {target_name} language quiz creator for {explanation_name} speakers.

Pick ONE NEW {target_name} word the learner likely hasn't studied yet, then create a 4-option multiple-choice quiz on its meaning.

{_history_section(history)}

{_exclusion_section(exclusion_list)}

Return a JSON object with this exact structure:

{{
  "source_text": "the new {target_name} word you picked",
  "question_text": "a question in {explanation_name} that QUOTES source_text by name and asks for its meaning. Substitute <WORD> with source_text. Template: \\"「<WORD>」の意味として最も適切なものはどれですか？\\" (when {explanation_name} is Japanese) or \\"What does <WORD> mean?\\" (when English)",
  "choices": ["choice 1", "choice 2", "choice 3", "choice 4"],
  "correct_index": <int 0-3 indicating which choice is correct>,
  "explanation": "brief explanation in {explanation_name} (under 200 chars)"{extra_schema}
}}

Rules:
- The chosen source_text MUST be different from every forbidden word listed above.
- {_level_hint(target_lang)}
- The question_text MUST quote source_text by name and ask for its meaning. NEVER phrase it as "which word means X" or any reverse direction; source_text is shown in the embed description, so the reverse direction would reveal the answer.
- All 4 choices are meanings in {explanation_name}. NEVER include a {target_name} word as a choice.
- Distractors should be confusable but clearly wrong.
- Keep each choice short (under 30 characters where possible, hard max 80).
- Randomize the correct answer's position.
- Explanation should be neutral reference-book tone (no character voice).{extra_rules}

Respond ONLY with the JSON object, no markdown fences, no extra text."""


def build_new_batch_prompt(
    target_lang: str,
    explanation_lang: str,
    history: list[str],
    exclusion_list: list[str],
    count: int,
) -> str:
    """互いに異なる未学習語 count 個のバッチ新出クイズ用 system prompt。"""
    target_name, explanation_name = lang_names(target_lang, explanation_lang)
    extra_schema = _extra_fields_schema(target_lang, target_name)
    extra_rules = _extra_fields_rules(target_lang, target_name)
    return f"""You are a {target_name} language quiz creator for {explanation_name} speakers.

Pick {count} DISTINCT NEW {target_name} words the learner likely hasn't studied yet, then create a 4-option multiple-choice quiz on the meaning of each.

{_history_section(history)}

{_exclusion_section(exclusion_list)}

Return a JSON array of exactly {count} objects, each with this exact structure:

[
  {{
    "source_text": "the new {target_name} word you picked",
    "question_text": "a question in {explanation_name} that QUOTES source_text by name and asks for its meaning. Substitute <WORD> with source_text. Template: \\"「<WORD>」の意味として最も適切なものはどれですか？\\" (when {explanation_name} is Japanese) or \\"What does <WORD> mean?\\" (when English)",
    "choices": ["choice 1", "choice 2", "choice 3", "choice 4"],
    "correct_index": <int 0-3 indicating which choice is correct>,
    "explanation": "brief explanation in {explanation_name} (under 200 chars)"{extra_schema}
  }}
]

Rules:
- The {count} source_text values MUST all be different from each other.
- Every source_text MUST be different from every forbidden word listed above.
- {_level_hint(target_lang)}
- Each question_text MUST quote its source_text by name and ask for its meaning. NEVER phrase it as "which word means X" or any reverse direction; source_text is shown in the embed description, so the reverse direction would reveal the answer.
- All 4 choices in each quiz are meanings in {explanation_name}. NEVER include a {target_name} word as a choice.
- Distractors should be confusable but clearly wrong.
- Keep each choice short (under 30 characters where possible, hard max 80).
- Randomize the correct answer's position in each quiz.
- Explanation should be neutral reference-book tone (no character voice).{extra_rules}

Respond ONLY with the JSON array, no markdown fences, no extra text."""
