# Language Teacher Discord Bot - 要件定義書

| 項目                   | 内容                                  |
| ---------------------- | ------------------------------------- |
| ドキュメントバージョン | 0.9 (チャンネル分離)                  |
| 作成日                 | 2026-05-24                            |
| 最終更新               | 2026-05-27                            |
| ステータス             | 実装中(Phase 4 までリリース済み / Phase 7 で 2 Bot 構成に再編 / Phase 8 で dev/prod 分離 / Phase 9 でチャンネル分離) |
| 対象プロダクト         | Language Teacher Discord Bots(英語先生Bot / 日本語先生Bot) |

---

## 1. 概要と目的

### 1.1 背景

日本人(あなた)と外国人パートナー(彼女)が、Discord 上で日常的に会話している。あなたは英語を、彼女は日本語をそれぞれ学習中で、会話の最中にわからない単語・表現が出てきた際、Discord の外で辞書や翻訳サイトを開いて調べる必要がある。これは会話の流れを止め、学習のモチベーションも下げる。

### 1.2 ゴール

- Discord 内で会話を中断せずに、単語・文章・文法の解説を受けられる状態を作る。
- 学習者の母語に合わせた解説で、効率的にインプットできるようにする。
- 調べた単語を蓄積し、週次でまとめて復習できるようにする。
- 2 人が同時に互いの学習を支援できる(自分が相手のために調べることも自然にできる)。

### 1.3 非ゴール(本プロジェクトでは扱わない)

- 音声・発音機能(将来検討)。
- 単語帳アプリのような長期 SRS(間隔反復)学習機能。
- 他言語(英語・日本語以外)への対応。
- 一般ユーザー(自分達 2 人以外)向けのサービス化。

---

## 2. ユーザー

### 2.1 ペルソナ A: 英語学習者(あなた)

- 母語: 日本語
- 学習言語: 英語
- 主なユースケース:
  - 彼女から英語メッセージを受け取り、わからない単語を調べる。
  - 彼女に伝えたい日本語の単語を、彼女向けに英語解説付きで共有する。

### 2.2 ペルソナ B: 日本語学習者(彼女)

- 母語: 英語(または他言語、UI 上は英語で対応)
- 学習言語: 日本語
- 主なユースケース:
  - あなたから日本語メッセージを受け取り、わからない単語を調べる。
  - あなたに伝えたい英語の単語を、あなた向けに日本語解説付きで共有する。

### 2.3 利用シーン

会話中に「これってどういう意味?」と思った瞬間に、Bot へメンションして即座に解説を得る。学習中の言語の Bot を呼ぶことで、自分のための調べ物にも、相手への教材提供にもなる。

---

## 3. スコープ

### 3.1 含むもの

- Discord 上での単語・文章・文法に関する自動回答。
- 英↔日 双方向の解説。
- 検索履歴の保存と週次レポート配信。
- 辞書ページへのリンク提供。

### 3.2 含まないもの

- 外部公開・他サーバーへの導入。
- Web UI、モバイルアプリ、メール通知などの Discord 外配信。
- 音声入出力。
- 課金ユーザー管理。

---

## 4. 機能要件

### 4.1 単語翻訳機能

- 入力: 単語 1 つ(例: `apple`, `林檎`)。
- 出力:
  - 訳語(母語の対訳)
  - 品詞
  - 簡単な意味説明
  - 使い方(コロケーション、レベル感のあるニュアンス)
  - 例文 2〜3 件(対訳付き)
  - 辞書ページへのリンク
- 利用 LLM: Gemini API(`gemini-3.1-flash-lite`)。

### 4.2 文章翻訳機能

- 入力: 複数語からなる文(例: `Could you pick me up at the station?`)。
- 出力:
  - 自然な訳文
  - 直訳(必要に応じて、ニュアンス理解の補助)
  - 重要表現の補足(1〜2 個)
- 利用 LLM: Gemini API(品質要求が高いため)。

### 4.3 文法解説機能

- 入力: 文法事項に関する質問(例: `would have p.p.の使い方`, `〜てしまう の意味`)。
- 出力:
  - 文法ルールの解説
  - 例文 2〜3 件(対訳付き)
  - 類似文法との違い(あれば)
- 利用 LLM: Gemini API(解説の正確性が重要なため)。

### 4.4 入力種別の自動判定

- 判定方式: **LLM による自動判定**(別途軽量 LLM 呼び出し or システムプロンプトでのルーティング)。
- 判定対象: 「単語」「文章」「文法質問」の 3 種。
- 失敗時の挙動: 判定が曖昧な場合は「単語」として処理し、結果に「文章として翻訳しますか?」のフォローを付ける。

### 4.5 Web リンク挿入

- リンク先:
  - 英語の単語: Cambridge Dictionary (`https://dictionary.cambridge.org/dictionary/english/{word}`)
  - 日本語の単語: Jisho.org (`https://jisho.org/search/{word}`)
- 実装方式: 単語文字列を URL エンコードしてリンク生成(API 呼び出し不要)。
- リンク到達性の確認: 行わない(404 でもユーザーが他で検索できれば実用上問題なしと判断)。

### 4.6 クエリログの記録

- 記録対象: **単語・文章・文法の全クエリ**(2026-05-24 変更: 当初は単語のみだったが、文章・文法も振り返り価値が高いと判断し全種記録に拡張)。
- 記録項目:
  - 種別(`kind`: word / sentence / grammar)
  - 検索した Discord ユーザー ID(と表示名)
  - 対象言語(`target_lang`: en / ja)
  - クエリ本文(`query_text`)
  - 結果サマリ(`result_summary`): word は訳語、sentence は自然訳、grammar はトピック名
  - 検索日時(JST)

### 4.7 週次レポート

- タイミング: 毎週日曜 21:00 JST。
- 投稿先: 専用チャンネル(`.env` の `REPORT_CHANNEL_ID` で指定)。
- 形式: 1 学習方向(`target_lang`)につき 1 つの Embed。中に 3 セクション(📘 単語 / 📝 文章 / 📚 文法)。
- **集計単位は target_lang のみ**(2026-05-24 変更):「誰が調べたか」は無視し、target_lang ベースで学習者にひも付ける。
  - 例: Chris が `視察` を調べても、`視察` は日本語学習者(Camille)のレポートに入る
  - 理由: 復習対象は「学んでいる言語の語彙」であり、querier は無関係
- 学習者名は `.env` の `EN_LEARNER_NAME` / `JA_LEARNER_NAME` で指定。
- 集計範囲: 今週(月曜 0:00 〜 実行時刻、JST)。
- 重複: 同じクエリが複数回検索されても 1 行にまとめ、検索回数を併記。
- 0 件の target_lang / kind は表示しない(ノイズ抑制)。

### 4.8 デイリークイズ機能(Phase 6)

- **配信タイミング**: 毎朝 8:00 JST(APScheduler の cron)。
- **配信単位**: 学習者ごとに個別問題(EN 学習者は英語、JA 学習者は日本語)。
- **1 日の問題数**: 2 問(復習 1 + 新出 1、両方クイズ形式)。
- **問題種別**: Phase 1 は word のみ。grammar は Phase 2 で曜日固定(日曜)案で追加予定。
- **出題形式**: 4 択ボタン(Discord Button Component)。
- **復習ソース**: `query_log` 履歴から、過去その学習者が調べた語を選定。
- **新出ソース**: LLM 1 回コールで「学習者の直近履歴 + 過去出題除外リスト」を渡し、同レベル相当の未学習語を提案。
- **回答権限**: 該当学習者本人のみ。他者のボタン押下はエフェメラル応答で弾く。
- **正解発表**: 本人がボタンを押した瞬間に即時(不正解でも一発で正解+解説を表示)。
- **未回答時**: 放置(自動で答えを出さない、統計用に `answered_at` NULL のまま残す)。
- **キャラクター付与**: なし。事典トーンで統一。

詳細仕様は 14 章を参照。

---

## 5. 非機能要件

### 5.1 可用性

- 24 時間稼働は不要。Mac 起動中・Bot プロセス起動中のみ稼働。
- Bot 停止中にメンションされた場合、起動後に再送してもらう運用(自動キュー不要)。

### 5.2 レスポンス時間目標

| 機能     | 目標応答時間 |
| -------- | ------------ |
| 単語翻訳 | 3 秒以内     |
| 文章翻訳 | 3 秒以内     |
| 文法解説 | 5 秒以内     |

すべて Gemini API(`gemini-3.1-flash-lite`)を利用。

応答に時間がかかる場合は、Discord の「考え中」インジケータ(typing indicator)で UX を維持する。

### 5.3 コスト

- 目標: 月額 **$0**(電気代を除く)。
- Gemini API は `gemini-3.1-flash-lite` の無料枠内で運用する前提。具体的なレート制限(RPM / RPD / TPM)は公式ドキュメントに明示されていないため、Phase 3 着手時に再確認する。
- 想定超過時の対応: 5 章 5.5 を参照。

### 5.4 プライバシー

- 会話履歴は Discord 上にのみ存在。Bot は単語検索ログ以外を保存しない。
- ログ DB はローカル(Mac 内)にのみ保存。クラウド送信は行わない。
- ユーザーが Bot に送信した内容(単語・文章・文法質問)は Gemini API 経由で Google に送られる前提を受け入れる。機微情報は Bot に送らない運用とする。

### 5.5 制約・フェイルセーフ

- Gemini API 失敗時: エラーメッセージを Discord 上に返す(例: "現在 API が利用できません。少し時間を置いて再試行してください")。リトライは 1 回まで自動実施。
- レート制限超過時: ユーザーに「明日また試して」と通知。

---

## 6. 技術スタック

| レイヤ             | 技術                           | 選定理由                                                    |
| ------------------ | ------------------------------ | ----------------------------------------------------------- |
| 言語               | Python 3.11+                   | discord.py の安定運用、LLM 周辺ライブラリの充実             |
| Discord ライブラリ | discord.py 2.x                 | Python での Discord Bot 開発のデファクト                    |
| LLM                | Gemini API(`gemini-3.1-flash-lite`) | 無料枠あり、日英品質が安定、思考モードなし                  |
| Gemini SDK         | `google-genai`                 | Google 公式 Python SDK                                      |
| データベース       | SQLite                         | 2 人運用ならファイル 1 つで十分。バックアップも容易         |
| スケジューラ       | APScheduler                    | Python ネイティブ、cron 式対応                              |
| 設定管理           | python-dotenv + YAML           | トークン類は `.env`、Bot 仕様は YAML で分離                 |
| パッケージ管理     | uv                             | 高速・ロックファイル管理が確実、Python バージョン管理も内包 |

### 6.1 LLM 選定の経緯

- 当初は Ollama(Local LLM)+ Gemini API のハイブリッドを計画。
- Phase 2 開始時、Local LLM 候補(Qwen 3.5 9B、Gemma 4 26B、Qwen 2.5 14B)を順に試したが、**それぞれ思考モードによる極端な遅延または日本語品質の問題**が判明。
- 2 人運用の小規模利用では Gemini 無料枠で十分賄えるため、**Gemini API 一本化に方針変更**(2026-05-24)。
- 当初 `gemini-3.5-flash` を採用したが、**Phase 4 完了後の運用テストで無料枠が 20 req/day しかないと判明**。1 クエリで API を 2 回(分類 + ハンドラ)叩く設計のため実質 10 問/日。`gemini-3.1-flash-lite` に切替(無料枠が桁違いに大きい "frontier-class lite")(2026-05-24)。
- 将来 Local LLM に戻すオプションは残す(プライバシー強化やオフライン対応が必要になった場合)。

---

## 7. システム構成

### 7.1 構成図(テキスト)

```
[Discord クライアント]
       │
       │ @英語先生Bot       │ @日本語先生Bot
       ▼                    ▼
┌────────────────────┐  ┌────────────────────┐
│ Bot: en_teacher    │  │ Bot: ja_teacher    │
│ target=en          │  │ target=ja          │
│ explanation=ja     │  │ explanation=en     │
│ 入力種別判定        │  │ 入力種別判定        │
└─────────┬──────────┘  └─────────┬──────────┘
          │                       │
          ▼                       ▼
        ┌────────────────────────────┐
        │       Gemini API           │
        │       (HTTPS)              │
        └─────────────┬──────────────┘
                      │
                ┌─────▼──────┐
                │  SQLite    │ ← 2 Bot で共有
                │ (検索・クイズログ)│
                └─────┬──────┘
                      │
            ┌─────────┴─────────┐
            ▼                   ▼
     ┌──────────────┐    ┌──────────────┐
     │ APScheduler  │    │ APScheduler  │
     │ (en_teacher) │    │ (ja_teacher) │
     └──────┬───────┘    └──────┬───────┘
            ▼                   ▼
   日次クイズ(8:00)       日次クイズ(8:00)
   週次レポート(日 21:00)  週次レポート(日 21:00)
```

### 7.2 2 Bot + Bot 識別による役割固定の根拠

- 初期は 1 Bot + 入力言語自動判定構成(2026-05-24 決定)で運用していたが、**英語話者ユーザーが「英語のこの単語を日本語で何ていうの?」と英語の単語を投げた場合、入力に日本語文字がないため "日本語話者向け" と誤判定され、漢字振り仮名のない日本語で回答が返ってしまう**という問題が判明。回答自体が読めない / 漢字の読み方が分からないため学習にならない。
- これを解決するため、**Bot 識別によって `target_lang` と `explanation_lang` の両方を固定する 2 Bot 構成に再編**(2026-05-26 決定)。
  - `BOT_ROLE=en_teacher`(英語先生Bot): target=en / explanation=ja。Cambridge リンク。
  - `BOT_ROLE=ja_teacher`(日本語先生Bot): target=ja / explanation=en。Jisho リンク。日本語の漢字には常に振り仮名付き。
- 振り分けルール:「ユーザーは自分が学んでいる言語の先生Bot にメンションする」のみ。入力文字種は分岐に使わない。
- 入力が target/explanation のどちらの言語でも受けるため、**逆引き対応**を word/sentence ハンドラのプロンプトで実装(入力が explanation_lang の語句なら target_lang equivalent を主見出しに、漢字なら振り仮名必須)。
- メリット:
  - 学習者の母語と学習対象が Bot 識別で明確に固定され、解説が確実に学習者の母語で返る。
  - 逆引きユースケース(母語の語をきっかけに学習対象言語の語を引く)が自然に扱える。
- トレードオフ:
  - Discord 開発者ポータルへの Bot 登録が 2 件必要。
  - プロセスが 2 つ(`docker-compose.yml` の 2 サービス)。

### 7.3 1 コードベース・2 サービス構成

- ソースは 1 つ。`BOT_ROLE` 環境変数(`en_teacher` / `ja_teacher`)で実行時の役割を決定。
- `src/config.py` の `load_bot_config()` が `BOT_ROLE` を読み、`(target_lang, explanation_lang, dictionary_url_template, learner_discord_id, learner_name)` をまとめて返す。
- `docker-compose.yml` に `bot-en` / `bot-ja` の 2 サービスを定義。`env_file` は `.env.en` / `.env.ja` を指定。`./data` ボリュームは両サービスで共有(SQLite を共有)。

### 7.4 プロセス起動

```bash
# Docker(両方一括)
docker compose up -d

# ローカル(個別)
BOT_ROLE=en_teacher uv run python src/main.py
BOT_ROLE=ja_teacher uv run python src/main.py
```

---

## 8. データモデル

### 8.1 SQLite スキーマ

```sql
CREATE TABLE query_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,               -- 'word' | 'sentence' | 'grammar'
    target_lang TEXT NOT NULL,        -- 'en' or 'ja' (検索対象の言語)
    discord_user_id TEXT NOT NULL,
    discord_user_name TEXT NOT NULL,
    query_text TEXT NOT NULL,         -- ユーザーが入力した単語/文/文法質問
    result_summary TEXT,              -- word=訳語 / sentence=自然訳 / grammar=トピック
    queried_at TEXT NOT NULL          -- ISO8601 (JST)
);

CREATE INDEX idx_query_log_queried_at ON query_log(queried_at);
CREATE INDEX idx_query_log_user_kind ON query_log(discord_user_id, target_lang, kind);

-- デイリークイズ機能用(Phase 6 で追加)
CREATE TABLE quiz_log (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_user_id    TEXT    NOT NULL,
    target_lang        TEXT    NOT NULL,  -- 'en' | 'ja'
    kind               TEXT    NOT NULL,  -- 'word' | 'grammar' (Phase 1 は word のみ)
    mode               TEXT    NOT NULL,  -- 'review' | 'new'
    source_text        TEXT    NOT NULL,  -- 出題対象 (単語 or 文法パターン)
    question_text      TEXT    NOT NULL,  -- 表示する問題文
    choices_json       TEXT    NOT NULL,  -- 4 択 (JSON 配列)
    correct_index      INTEGER NOT NULL,  -- 0-3
    explanation        TEXT    NOT NULL,  -- 解説
    message_id         TEXT,              -- Discord メッセージ ID (button 受付用)
    delivered_at       TEXT    NOT NULL,  -- ISO8601 (JST)
    answered_at        TEXT,              -- 回答時刻、未回答なら NULL
    user_answer_index  INTEGER,           -- 0-3、未回答なら NULL
    is_correct         INTEGER            -- 0/1、未回答なら NULL
);

CREATE INDEX idx_quiz_user_delivered ON quiz_log(discord_user_id, delivered_at DESC);
CREATE INDEX idx_quiz_message        ON quiz_log(message_id);
CREATE INDEX idx_quiz_user_source    ON quiz_log(discord_user_id, source_text);
```

### 8.2 設定(`.env.{en,ja}` 経由 + コード定数)

`BOT_ROLE` を起点に `src/config.py` の `load_bot_config()` が他の固定値を導出する。Bot ごとに別 env ファイル(`.env.en` / `.env.ja`)を用意し、`docker-compose.yml` でサービスごとに `env_file` を割り当てる。

| 設定項目                    | 例                                                           | 配置                   |
| --------------------------- | ------------------------------------------------------------ | ---------------------- |
| Bot ロール                  | `BOT_ROLE=en_teacher` / `ja_teacher`                         | `.env.{en,ja}`         |
| Discord Bot トークン        | `DISCORD_BOT_TOKEN=xxx`(Bot ごとに別)                       | `.env.{en,ja}`         |
| Gemini API キー             | `GEMINI_API_KEY=xxx`                                         | `.env.{en,ja}`         |
| 英→日 辞書 URL テンプレート | `https://dictionary.cambridge.org/dictionary/english/{word}` | `src/config.py` 定数(`en_teacher` で採用) |
| 日→英 辞書 URL テンプレート | `https://jisho.org/search/{word}`                            | `src/config.py` 定数(`ja_teacher` で採用) |
| レポート投稿チャンネル ID   | `REPORT_CHANNEL_ID=xxx`(各 Bot で別チャンネル ID)            | `.env.{en,ja}`         |
| クイズ投稿チャンネル ID     | `QUIZ_CHANNEL_ID=xxx`(各 Bot で別チャンネル ID、未設定ならクイズ無効化) | `.env.{en,ja}`(en/ja で別チャンネル) |
| 英語学習者の Discord ID     | `EN_LEARNER_DISCORD_ID=xxx`                                  | `.env.{en,ja}`(`en_teacher` で使用) |
| 日本語学習者の Discord ID   | `JA_LEARNER_DISCORD_ID=xxx`                                  | `.env.{en,ja}`(`ja_teacher` で使用) |
| 英語学習者の表示名          | `EN_LEARNER_NAME=Yura`                                       | `.env.{en,ja}`         |
| 日本語学習者の表示名        | `JA_LEARNER_NAME=Camille`                                    | `.env.{en,ja}`         |

---

## 9. Bot 仕様

### 9.1 発火条件

- Bot へのメンションをトリガとする(例: `@英語先生Bot apple`)。
- メンション以外のメッセージには反応しない(誤動作防止)。
- どちらの Bot を呼ぶかでユーザーの母語と学習対象が決まる:
  - `en_teacher`(英語先生Bot): target=en / explanation=ja(日本語で解説、Cambridge リンク)
  - `ja_teacher`(日本語先生Bot): target=ja / explanation=en(英語で解説、Jisho リンク。漢字には振り仮名)
- 入力文字種は分岐に使わない。入力が母語(`explanation_lang`)であっても、Bot は target_lang の equivalent を主見出しに据えて返す(逆引き対応)。

### 9.2 入力 → 出力の例

#### 例 1: 単語(英語先生Bot に英単語 → 日本語解説)

```
入力: @英語先生Bot apple
```

```
出力 (Discord Embed):
─────────────────────────────────
📘 apple  (noun)
─────────────────────────────────
訳: リンゴ

意味: 赤や緑の皮を持つ果物。バラ科の植物の実。

使い方:
- "an apple a day keeps the doctor away" (慣用句)
- 比喩で「都会」を指すこともある(the Big Apple)

例文:
1. I ate an apple for breakfast.
   朝食にリンゴを食べた。
2. She picked apples from the tree.
   彼女は木からリンゴをもいだ。

🔗 Cambridge Dictionary で見る
─────────────────────────────────
```

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

### 9.3 Embed の基本フォーマット

- Title: 主見出し(target_lang の語)+ 品詞(単語の場合)。日本語先生Bot で主見出しに漢字を含むときは `【ふりがな】` を必ず付与。
- Description: 訳・解説本体
- Fields: 例文・リンクなど
- Color: target_lang で色分け(target=en は青、target=ja は赤)

### 9.4 逆引きユースケース

例: 日本語先生Bot に英単語を投げる(英語話者が「これって日本語で何ていうの?」と聞くケース)。

```
入力: @日本語先生Bot apple
```

```
出力:
📘 りんご  (noun)
─────────────────────────────────
Translation: apple

Meaning: A round, sweet fruit. Common in everyday Japanese.

Usage: written 「りんご」 in hiragana for everyday contexts; 「林檎」 in kanji is rarer.

Examples:
1. りんごを食べた。
   I ate an apple.
2. このりんごは甘い。
   This apple is sweet.

🔗 Jisho.org で見る
```

漢字を含む主見出しになった場合(例: 日本語先生Bot に "desk" → 「机【つくえ】」)、振り仮名がタイトルに必ず付く。

---

## 10. 週次レポート仕様

### 10.1 配信条件

- 実行時刻: 毎週日曜 21:00(Asia/Tokyo)。
- 実行主体: APScheduler が Bot プロセス内で動作。
- 投稿先: 専用チャンネル(`.env` の `REPORT_CHANNEL_ID` で指定)。
- 集計単位: ユーザー × 学習方向(`target_lang` = en or ja)で分けて投稿。

### 10.2 出力フォーマット例

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

## 11. 制約事項・前提

### 11.1 運用前提

- Mac が起動しており、Bot プロセスが立ち上がっている時のみ機能する。
- 自宅の電気/ネットワークが安定していることを前提とする。
- Gemini API の到達性を前提とする(オフラインでは動作しない)。

### 11.2 外部依存

- Discord API のレート制限(基本的に問題にならない規模だが、メッセージ送信は 5 req/sec 程度を目安に)。
- Gemini API の無料枠超過時はエラーレスポンスを返し、ユーザーに「明日また試して」と通知する。

### 11.3 セキュリティ

- Discord Bot トークン、Gemini API キーは `.env` に格納し、`.gitignore` で除外する。
- リポジトリへの誤コミット防止のため、`pre-commit` フックで秘密情報スキャンを将来導入検討。

---

## 12. 開発フェーズ計画

各フェーズは「動く状態でレビューを受ける」を最小単位とする。フェーズ完了時に動作確認 → 次フェーズ着手。

### Phase 1: Bot 起動と最小応答 (推定 0.5 日)

- Discord 開発者ポータルで Bot 1 体を登録(まずは 1 体で開始)。
- `discord.py` で接続、メンションに対して "pong" を返すだけの実装。
- `.env` 読み込み、基本ロギング。

**完了条件:** Discord 上で `@Bot ping` → `pong` が返る。

### Phase 2: Gemini 連携 + 単語翻訳 + Web リンク (推定 1〜2 日)

- Gemini API 連携(`google-genai` SDK)。
- 単語翻訳プロンプト作成。
- 出力を Discord Embed に整形し、辞書リンク(Cambridge / Jisho)を付与。

**完了条件:** `@Bot apple` → 訳・例文・Cambridge リンク付き Embed が返る。

### Phase 3: 文章 / 文法対応 + 入力種別判定 (推定 1〜2 日)

- 入力種別判定ロジック(LLM ベース or 簡易ルール)を実装。
- 文章翻訳・文法解説のプロンプト作成と整形。

**完了条件:** 単語 / 文章 / 文法、いずれの入力にも適切に応答する。

### Phase 4: ログ記録 + 週次レポート (推定 1〜2 日)

- SQLite スキーマ作成、単語検索時のログ保存。
- APScheduler で週次ジョブを設定。
- 集計クエリ + Embed 投稿。

**完了条件:** 1 週間運用後、日曜 21:00 に正しい集計レポートが届く(初回はテスト用に手動トリガで確認)。

### Phase 5(任意): 運用改善

- Embed の色・絵文字調整。
- エラー時のフォールバック整備。
- launchd / systemd での常駐化(必要なら)。

### Phase 6: デイリークイズ機能(推定 2〜3 日)

- `.env` に `QUIZ_CHANNEL_ID` / `EN_LEARNER_DISCORD_ID` / `JA_LEARNER_DISCORD_ID` を追加。
- SQLite に `quiz_log` テーブルを追加(8.1 参照)。
- APScheduler に毎朝 8:00 JST cron を追加。
- 出題ロジック(復習選定 + 新出 LLM 生成)を実装。
- 4 択ボタンを含む Embed を投稿、本人のみ受付・即時採点。
- Phase 1 サブ: word のみ実装。Phase 2 サブ: grammar 追加(日曜固定)。

**完了条件:** 毎朝 8:00 に各学習者へ 2 問配信され、本人がボタンを押した瞬間に正解 + 解説が表示される。1 週間運用して重複防止・履歴ゼロフォールバックが想定通り動くことを確認する。

### Phase 7: 2 Bot 構成への再編(本フェーズで対応)

- 入力文字種ベースの言語自動判定では、**英語話者ユーザーが英単語を投げた時に日本語話者向けと誤判定**される不具合が判明。
- `BOT_ROLE`(`en_teacher` / `ja_teacher`)で `target_lang` / `explanation_lang` を完全固定する 2 Bot 構成に再編。
- `src/config.py` を新設、`docker-compose.yml` を 2 サービス化、`.env.{en,ja}` で env を分離。
- `word_handler` / `sentence_handler` のプロンプトに逆引き対応を追加(入力が母語でも target_lang の主見出しを返す)。
- `grammar_handler` を caller-controlled に揃え、LLM 側自動判定を撤去。
- クイズ・週次レポートを各 Bot の担当学習者のみに限定。

**完了条件:** 英語話者が日本語先生Bot に英単語 / 英文を投げた際に、target=ja の主見出し(漢字なら振り仮名付き)+ 英語解説が返ること。

### Phase 8: dev/prod 環境分離(本フェーズで対応)

- 本番が常時稼働しているため、検証なしに main へ push して即反映される運用に検証ステージを挟みたい。
- 同一 EC2(`i-08d32da47bbc237aa`)上に `/opt/language-teacher/{prod,dev}` を並存させ、Compose project name(`lt-prod` / `lt-dev`)と SSM プレフィックス(`/language-teacher/{prod,dev}/*`)で隔離。
- `main` push → prod / `develop` push → dev に GitHub Actions が振り分けてデプロイ。
- dev は専用 Discord サーバー + 別 Bot 2 個を使用し、本番ユーザーから完全隔離。
- 設計判断とシステム構成は `docs/aws-infrastructure.md` に記録。

**完了条件:** `develop` ブランチへの push で dev 環境のみが更新され、本番には影響しないこと。dev 用 Discord サーバーで両 Bot が応答すること。prod の `data/` と dev の `data/` が物理的に独立した SQLite ファイルとして存在すること。

### Phase 9: クイズ・週次レポートのチャンネル分離(本フェーズで対応)

- 単一チャンネルに英語学習者向け / 日本語学習者向けのクイズと週次レポートが混在し、各学習者にとって自分のメンション以外がノイズになる。特にクイズは毎朝 2 種類が並んで投稿され、視認性が悪い。
- 解決: Bot ロールごとに専用チャンネルを持たせる(`#en-quiz` / `#ja-quiz` / `#en-report` / `#ja-report`)。
- `main.py` のコードは変更不要(`QUIZ_CHANNEL_ID` / `REPORT_CHANNEL_ID` を読むだけ)。各 Bot の `.env` に違う値が入る形にする。
- SSM Parameter Store を以下に拡張(prod/dev 各 11 個):
  - `en-quiz-channel-id`, `ja-quiz-channel-id`, `en-report-channel-id`, `ja-report-channel-id`(計 4 個)
- `scripts/deploy.sh` で 4 個を取得し、各 `.env` に Bot ロールに応じた値を書き分け。

**完了条件:** 英語学習者のチャンネルには英語学習者向けクイズ・レポートのみが投稿される。日本語学習者のチャンネルも同様。両者が混ざらないこと。

---

## 13. 未決事項 / 今後の検討

| #    | 項目                                         | 内容                                                                                                      | 決定タイミング |
| ---- | -------------------------------------------- | --------------------------------------------------------------------------------------------------------- | -------------- |
| 13.1 | ~~Local LLM の最終モデル~~                   | **撤回: Gemini API 一本化に変更**(2026-05-24)。Local LLM 候補がいずれも品質・速度で実用に満たなかったため | 解決済み       |
| 13.2 | 入力種別判定の方式                           | LLM 判定が遅い場合、文字数・空白数ベースの簡易判定にフォールバック                                        | Phase 3 実測後 |
| 13.3 | ~~言語の自動判定~~                           | **撤回**(2026-05-26): 文字種ベース判定では英語話者の英単語入力を誤判定するため、Bot 識別での固定(`BOT_ROLE`)に再変更。Phase 7 で対応 | 撤回済み       |
| 13.4 | ~~レポート時のチャンネル指定~~               | **決定: 専用チャンネル**(`.env` の `REPORT_CHANNEL_ID` で指定。各 Bot が自学習者の分のみ投稿)              | 解決済み       |
| 13.5 | ~~過去履歴のリセット運用~~                   | **決定: 永久保持**(2 人運用なら DB サイズ無視可。長期振り返りに使える)                                    | 解決済み       |
| 13.6 | 将来拡張候補                                 | 音声(TTS)、~~復習クイズ~~ (Phase 6 で着手、2026-05-25)、Anki エクスポート                                  | 一部解決済み   |
| 13.7 | ~~パッケージ管理ツール~~                     | **決定: uv 採用** (2026-05-24)                                                                            | 解決済み       |
| 13.8 | ~~「入力言語と逆の言語で解説」の明示オプション~~ | **解決済み**(2026-05-26): Phase 7 の逆引き対応によりオプション不要。Bot 識別で explanation_lang が決まるため | 解決済み       |

---

## 14. デイリークイズ仕様(Phase 6)

### 14.1 配信

- 実行時刻: 毎朝 8:00(Asia/Tokyo)。
- 実行主体: APScheduler の cron(週次レポートと同じ仕組み)。
- 投稿先: `.env` の `QUIZ_CHANNEL_ID` で指定された専用チャンネル。
- 未設定時の挙動: クイズ機能を無効化し警告ログ出力(`REPORT_CHANNEL_ID` 未設定時と同じ防御パターン)。

### 14.2 学習者の特定と個別化

- 学習者は 2 名(英語学習者 / 日本語学習者)を `.env` の `EN_LEARNER_DISCORD_ID` / `JA_LEARNER_DISCORD_ID` で指定。
- 各学習者向けに別問題セット(`target_lang` 別)を生成。
- メンションは Discord User ID 形式(`<@id>`)で行う。
- 表示名は引き続き `EN_LEARNER_NAME` / `JA_LEARNER_NAME` を使用(Embed のタイトル等)。

### 14.3 1 日の問題構成

- 通常: 復習 1 問 + 新出 1 問 = 計 2 問。
- フォールバック(履歴ゼロ時): 新出 1 問のみ。
- Phase 1 サブ: 両問とも word。grammar は Phase 2 サブで日曜固定追加予定。

### 14.4 復習問題の選定

1. `query_log` で当該学習者(`target_lang` 一致)の検索履歴を取得。
2. `quiz_log` で直近 14 日に出題した語(`source_text`)を除外。
3. 残った候補からランダムに 1 語を選定。
4. 選定された語について LLM に「4 択問題 + 解説」を生成依頼。

### 14.5 新出問題の選定・生成

1. 当該学習者の `query_log` 履歴(直近 30 件)を取得。
2. `quiz_log` の全期間で過去出題した `source_text` を除外リストに加える。
3. `query_log` にすでにある語(=既学習)も除外リストに加える。
4. LLM 1 回コールで以下を一括生成:
   - 履歴と除外リストを渡し、同レベル相当の未学習語を 1 つ選定。
   - その語の 4 択問題(正解 1 + 引っ掛け 3)。
   - 解説。
5. 履歴ゼロ時: 「CEFR A1-A2 相当の入門単語から 1 つ」とフォールバック指示。

### 14.6 4 択選択肢の構造

- 4 つの選択肢は LLM が一括生成する `choices_json` 配列(JSON 文字列で保存)。
- 正解インデックス(`correct_index`)は 0-3。
- 各選択肢は Discord Button のラベル表示制約(80 文字)に収まる短さ。

### 14.7 回答受付・採点フロー

1. クイズ投稿時、Embed + Button 4 つを含むメッセージを送信。
2. `quiz_log` に `delivered_at` / `message_id` 込みでレコード作成(`answered_at` 等は NULL)。
3. ユーザーがボタンを押したら:
   - `interaction.user.id` が当該学習者の ID と一致するか検証。
   - 不一致なら ephemeral 応答で「これはあなたのクイズじゃないよ」と返す。
   - 一致なら、選択肢インデックスを `correct_index` と比較。
   - `quiz_log` を `answered_at` / `user_answer_index` / `is_correct` で UPDATE。
   - 正解/不正解にかかわらず、即時に正解と解説を含む応答を返す(チャンスは 1 回のみ)。

### 14.8 重複防止

- **復習**: 直近 14 日以内に出題した語は除外(Spaced Repetition の 2 週間サイクル相当)。
- **新出**: 全期間で過去出題した語 + `query_log` にある語をすべて除外(未学習を保証)。

### 14.9 履歴ゼロ時のフォールバック

- 復習対象が 0 件のとき、その日は新出 1 問のみ出題(無理に 2 問にはしない)。
- 履歴が 1 件以上あれば通常通り「復習 1 + 新出 1」。
- 学習者が Bot を使い始めて履歴が蓄積されるにつれて、自然に通常運用に移行。

### 14.10 未回答時の扱い

- 学習者が回答しないまま時間が経過しても、自動で答えを表示しない。
- `quiz_log` のレコードは `answered_at` / `user_answer_index` / `is_correct` が NULL のまま残る。
- 統計用にこれら未回答レコードも保持。
- 古いクイズメッセージのボタンも引き続き押せる(押せば正解が表示される)。

### 14.11 キャラクター付与

- ぐりぞーキャラの口調・反応は付与しない。事典トーンで統一。
- Embed の文言・解説はすべてニュートラルな解説調。

### 14.12 表示例(イメージ)

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

---

## 付録 A: 用語集

| 用語        | 意味                                                                 |
| ----------- | -------------------------------------------------------------------- |
| Embed       | Discord の構造化メッセージ表示形式。タイトル・色・フィールドを持つ。 |
| メンション  | Discord で `@ユーザー名` の形でユーザー / Bot を呼び出す機能。       |
| target_lang | 検索対象単語の言語(`en` / `ja`)。レポートの集計単位にも使う。        |

## 付録 B: 想定ディレクトリ構成(参考、最終決定は設計フェーズで)

```
language-teacher/
├── REQUIREMENTS.md           # 本ドキュメント
├── README.md                 # セットアップ手順(後で作成)
├── .env.example              # トークン記入例
├── .gitignore
├── pyproject.toml            # 依存関係
├── src/
│   ├── main.py               # discord.py のエントリ
│   ├── handlers/             # 単語 / 文章 / 文法 ハンドラ
│   ├── llm/                  # Gemini クライアント
│   ├── db/                   # SQLite アクセス(Phase 4 で追加)
│   └── reports/              # 週次レポート生成(Phase 4 で追加)
├── data/
│   └── language_teacher.db   # SQLite 本体(.gitignore)
└── tests/
```
