# Language Teacher Discord Bot — Bot 挙動仕様

---

## 1. Bot 仕様

### 1.1 発火条件

- Bot へのメンションをトリガとする(例: `@英語先生Bot apple`)。
- メンション以外のメッセージには反応しない(誤動作防止)。
- どちらの Bot を呼ぶかでユーザーの母語と学習対象が決まる:
  - `en_teacher`(英語先生Bot): target=en / explanation=ja(日本語で解説、Cambridge リンク)
  - `ja_teacher`(日本語先生Bot): target=ja / explanation=en(英語で解説、Jisho リンク。漢字には振り仮名)
- 入力文字種は分岐に使わない。入力が母語(`explanation_lang`)であっても、Bot は target_lang の equivalent を主見出しに据えて返す(逆引き対応)。

### 1.2 入力 → 出力の例

#### 例 1: 単語(英語先生Bot に英単語 → 日本語解説)

```
入力: @英語先生Bot apple
```

```
出力 (Discord Embed):
─────────────────────────────────
📘 apple                          ← Title (= 入力語)
─────────────────────────────────
apple (noun)                      ← Field 名(語義の見出し。複数語義なら【1】等を前置)
**訳**: リンゴ

1. I ate an apple for breakfast.
    → 朝食にリンゴを食べた。
2. She picked apples from the tree.
    → 彼女は木からリンゴをもいだ。

🔗
[辞書で見る](Cambridge のリンク)    ← Field
─────────────────────────────────
            via gemini-3.1-flash-lite   ← フッター(応答モデル)
```

> 注: 複数の明確な意味を持つ語(例 `bank`)は語義(Field)が複数並び、各 Field 名に `【1】` `【2】` が付く。「訳語 + 例文」のみで構成し、独立した「意味」「使い方」欄は持たない。

#### 例 2: 文章(英語先生Bot に英文 → 日本語解説)

```
入力: @英語先生Bot Could you pick me up at the station?
```

```
出力:
訳: 駅まで迎えに来てもらえますか?

直訳: あなたは駅で私をピックアップしてもらえますか?

ポイント:
- "pick someone up" = 車などで誰かを迎えに行く
- "Could you 〜?" は丁寧な依頼
```

#### 例 3: 文法(日本語先生Bot に日本語文法質問 → 英語解説)

```
入力: @日本語先生Bot What does 〜てしまう mean?
```

```
出力:
〜てしまう has two main meanings:

1. Completion: emphasizes that an action is fully done.
   例: 宿題を全部やってしまった。 (I finished all the homework.)

2. Regret / unintended result: something happened that you didn't want.
   例: 寝坊してしまった。 (I overslept (and feel bad about it).)

In casual speech, 〜てしまう often becomes 〜ちゃう.
   例: 食べちゃった。 (I ate it (oops).)
```

### 1.3 Embed の基本フォーマット

Embed は種別(word / sentence / grammar)ごとに構造が異なる。共通点は色分けとフッター。

- **Color**: target_lang で色分け(target=en は青、target=ja は赤)。
- **Footer**: 応答した実モデルを `via {モデル名}`(OpenRouter はプロバイダ名併記)で表示。
- **単語(word)**:
  - Title = `📘 {入力語}`(ユーザーが送った語をそのままエコー。品詞・振り仮名は付けない)。
  - 各語義を 1 Field とする。Field 名 = `{見出し語}【ふりがな】 (品詞)`。複数語義なら `【1】` `【2】` を前置。振り仮名は日本語先生Bot で見出し語に漢字を含む場合のみ。
  - 末尾に `🔗` Field(辞書リンク)。
- **文章(sentence)**:
  - Title = `📝 {原文}`。Description = `【ふりがな】`(日本語の原文に漢字を含む場合のみ)。
  - Fields = 訳 / 直訳(あれば) / ポイント(あれば)。
- **文法(grammar)**:
  - Title = `📚 {トピック}`。
  - Fields = 解説 / 例文(あれば) / 関連(あれば)。
- ラベルは explanation_lang で出し分け(日本語なら「訳/直訳/ポイント/解説/例文/関連/辞書で見る」、英語なら "Translation/Literal/Key Points/Explanation/Examples/Related/View in dictionary")。

### 1.4 逆引きユースケース

例: 日本語先生Bot に英単語を投げる(英語話者が「これって日本語で何ていうの?」と聞くケース)。

```
入力: @日本語先生Bot apple
```

```
出力:
📘 apple                          ← Title (= 入力語をエコー)
─────────────────────────────────
りんご (noun)                      ← Field 名(target_lang の見出し語 + 品詞)
**Translation**: apple

1. りんごを食べた。
    → I ate an apple.
2. このりんごは甘い。
    → This apple is sweet.

🔗
[View in dictionary](Jisho のリンク)
─────────────────────────────────
            via gemini-3.1-flash-lite
```

漢字を含む見出し語になった場合(例: 日本語先生Bot に "desk" → 見出し語「机」)、Field 名に振り仮名が付く(`机【つくえ】 (noun)`)。振り仮名が付くのは Title ではなく語義の Field 名。

---

## 2. 週次レポート仕様

### 2.1 配信条件

- 実行時刻: 毎週日曜 21:00(Asia/Tokyo)。
- 実行主体: APScheduler が Bot プロセス内で動作。
- 投稿先: 専用チャンネル(`.env` の `REPORT_CHANNEL_ID` で指定)。
- 集計単位: ユーザー × 学習方向(`target_lang` = en or ja)で分けて投稿。

### 2.2 出力フォーマット例

```
📚 今週の学習サマリ
あなた / 英語学習 (EN → JA)
2026-05-19 〜 2026-05-24

📘 調べた単語 (18 語)
• apple — りんご (×2)
• pick up — 迎えに行く (×1)
...

📝 翻訳した文章 (5 件)
• Could you pick me up at the station? — 駅まで迎えに来てもらえますか?
• I want to learn Japanese with you. — あなたと日本語を学びたい。
...

📚 学んだ文法 (3 件)
• would have p.p.
• present perfect の用法
...
```

- ユーザー × 学習方向(`target_lang`)ごとに 1 Embed。
- 3 セクション(word / sentence / grammar)を持つが、0 件のセクションは省略。
- 1 セクション内が 50 件を超える場合は上位 50 件まで表示し、残件数を併記。

---

## 3. デイリークイズ仕様

### 3.1 配信

- 実行時刻: 毎朝 8:00(Asia/Tokyo)。
- 実行主体: APScheduler の cron(週次レポートと同じ仕組み)。
- 投稿先: `.env` の `QUIZ_CHANNEL_ID` で指定された専用チャンネル。
- 未設定時の挙動: クイズ機能を無効化し警告ログ出力(`REPORT_CHANNEL_ID` 未設定時と同じ防御パターン)。

### 3.2 学習者の特定と個別化

- 学習者は 2 名(英語学習者 / 日本語学習者)を `.env` の `EN_LEARNER_DISCORD_ID` / `JA_LEARNER_DISCORD_ID` で指定。
- 各学習者向けに別問題セット(`target_lang` 別)を生成。
- メンションは Discord User ID 形式(`<@id>`)で行う。
- 表示名は引き続き `EN_LEARNER_NAME` / `JA_LEARNER_NAME` を使用(Embed のタイトル等)。

### 3.3 1 日の問題構成

- 通常: 復習 1 問 + 新出 1 問 = 計 2 問。
- フォールバック(履歴ゼロ時): 新出 1 問のみ。
- 出題は word のみ。

### 3.4 復習問題の選定

1. `query_log` で当該学習者(`target_lang` 一致)の検索履歴を取得。
2. `quiz_log` で直近 14 日に出題した語(`source_text`)を除外。
3. 残った候補からランダムに 1 語を選定。
4. 選定された語について LLM に「4 択問題 + 解説」を生成依頼。

### 3.5 新出問題の選定・生成

1. 当該学習者の `query_log` 履歴(直近 30 件)を取得。
2. `quiz_log` の全期間で過去出題した `source_text` を除外リストに加える。
3. `query_log` にすでにある語(=既学習)も除外リストに加える。
4. LLM 1 回コールで以下を一括生成:
   - 履歴と除外リストを渡し、同レベル相当の未学習語を 1 つ選定。
   - その語の 4 択問題(正解 1 + 引っ掛け 3)。
   - 解説。
5. 履歴ゼロ時: 「CEFR A1-A2 相当の入門単語から 1 つ」とフォールバック指示。

### 3.6 4 択選択肢の構造

- 4 つの選択肢は LLM が一括生成する `choices_json` 配列(JSON 文字列で保存)。
- 正解インデックス(`correct_index`)は 0-3。
- 各選択肢は Discord Button のラベル表示制約(80 文字)に収まる短さ。

### 3.7 回答受付・採点フロー

1. クイズ投稿時、Embed + Button 4 つを含むメッセージを送信。
2. `quiz_log` に `delivered_at` / `message_id` 込みでレコード作成(`answered_at` 等は NULL)。
3. ユーザーがボタンを押したら:
   - `interaction.user.id` が当該学習者の ID と一致するか検証。不一致なら ephemeral 応答で「これはあなたのクイズじゃないよ / This isn't your quiz.」と返す。
   - すでに回答済み(`answered_at` が非 NULL)なら ephemeral 応答で「もう回答済みだよ / You've already answered.」と返す。
   - 一致かつ未回答なら、選択肢インデックスを `correct_index` と比較。
   - `quiz_log` を `answered_at` / `user_answer_index` / `is_correct` で UPDATE。
   - 正解/不正解にかかわらず、即時に正解と解説を含む応答を**公開メッセージ**で返す(チャンスは 1 回のみ)。正解時は `✅ 正解! / ✅ Correct!`、不正解時は `❌ 不正解 / ❌ Not quite` に「選んだ答え」と「正解」を併記。
4. 回答後、その日の配信分をすべて回答し終え、かつ追加枠が未使用なら追加クイズ(おかわり)プロンプトを `followup` で提示する(3.13)。

### 3.8 重複防止

- **復習**: 直近 14 日以内に出題した語は除外(Spaced Repetition の 2 週間サイクル相当)。
- **新出**: 全期間で過去出題した語 + `query_log` にある語をすべて除外(未学習を保証)。

### 3.9 履歴ゼロ時のフォールバック

- 復習対象が 0 件のとき、その日は新出 1 問のみ出題(無理に 2 問にはしない)。
- 履歴が 1 件以上あれば通常通り「復習 1 + 新出 1」。
- 学習者が Bot を使い始めて履歴が蓄積されるにつれて、自然に通常運用に移行。

### 3.10 未回答時の扱い

- 学習者が回答しないまま時間が経過しても、自動で答えを表示しない。
- `quiz_log` のレコードは `answered_at` / `user_answer_index` / `is_correct` が NULL のまま残る。
- 統計用にこれら未回答レコードも保持。
- 古いクイズメッセージのボタンも引き続き押せる(押せば正解が表示される)。

### 3.11 キャラクター付与

- ぐりぞーキャラの口調・反応は付与しない。事典トーンで統一。
- Embed の文言・解説はすべてニュートラルな解説調。

### 3.12 表示例(イメージ)

```
出題 (8:00 JST 投稿例):
─────────────────────────────────
🧩 今日のクイズ (1/2) — 復習
@Chris

次の意味として正しいのはどれ?

「awkward」

[ ぎこちない ] [ 賢明な ] [ 機敏な ] [ 明確な ]
─────────────────────────────────

(Chris が「ぎこちない」を押す)

応答 (Chris の押下直後):
─────────────────────────────────
✅ 正解!
awkward = ぎこちない / 気まずい

解説: 場の空気が悪く居心地が悪い様子、または身体の動きが不自然な様子を表す形容詞。
─────────────────────────────────
```

### 3.13 追加クイズ(おかわり)

学習意欲のある日にもっと解けるようにする、ユーザー駆動の追加出題。

- **発火条件**: その日(JST)に配信されたクイズを学習者が**すべて回答し終えた**直後。かつその日まだ追加枠を使っていないこと(`quiz_addon` テーブルで判定)。
- **提示**: 採点応答の後に `followup` で「🔥 もっとやる? / 🔥 Want more?」のメッセージ + ボタン(`+1` / `+2` / `+3` / なし)を出す。
- **本人検証**: ボタンの `custom_id` に user_id と target_lang を埋め込み、押下者が本人かを検証。不一致なら ephemeral で弾く。
- **1 日 1 回制限**: ボタン押下時に `quiz_addon` へ当日分を記録(`INSERT OR IGNORE`)。同日 2 度目の要求は「今日はもう追加済みだよ / Already added today.」で弾く。`なし(0)` を選んでも枠は消費する。
- **生成**: 選んだ数 `count`(1〜3)の**新出**クイズを 1 回のバッチ LLM コールで生成(`generate_new_quiz_batch`)。除外リスト(過去出題 + 既学習語)は 1 度だけ取得し、互いに異なる語を選ぶ。1 問ずつ生成するより API コールを削減する。
- **Embed**: タイトルは「追加クイズ / Bonus Quiz」表記(通常の「今日のクイズ / Daily Quiz」と区別)。出題・採点フローは通常クイズと同一。
- **未充足時**: バッチで `count` 個揃わなかった場合は揃った分だけ投稿する(重複は出さない)。
