# Threads 完全自動投稿システム

> MacBookを閉じたまま、朝8時に投稿が出る。
> エンジニアじゃなくても、AIと一緒に作れた仕組みの配布版です。

---

## このシステムでできること

- **自動投稿**：毎日 08:00 / 12:00 / 17:00 に Threads へ自動投稿（GitHub Actions）
- **統計収集**：毎日 23:00 に全投稿のインプレッション・いいね・リプライを自動収集
- **バズ分析**：週1回、TOP3/BOTTOM3を自動分析してレポートを出力
- **週次サイクル**：日曜夜30分で来週21本分の投稿を準備して登録するだけ

---

## セットアップ手順

### STEP 1：このリポジトリをテンプレートとして使う

右上の「Use this template」→「Create a new repository」をクリック。
リポジトリ名は `threads-automation` など分かりやすい名前で。**Private** を推奨。

### STEP 2：Threads API の設定

詳細な手順は購入した記事の **STEP 1** を参照してください。

取得が必要なもの：
- `THREADS_ACCESS_TOKEN`
- `THREADS_USER_ID`
- `THREADS_APP_ID`

### STEP 3：GitHub Secrets に登録

リポジトリの `Settings` → `Secrets and variables` → `Actions` から以下を登録：

| Secret名 | 値 |
|---|---|
| `THREADS_ACCESS_TOKEN` | Threads APIのアクセストークン |
| `THREADS_USER_ID` | ThreadsのユーザーID |
| `THREADS_APP_ID` | MetaアプリのID |

### STEP 4：GitHub Actions を有効化

リポジトリの `Actions` タブを開き、ワークフローを有効にする。

自動実行スケジュール：
- **投稿**：毎日 08:00 / 12:00 / 17:00（JST）
- **統計収集**：毎日 23:00（JST）

### STEP 5：投稿文を登録する

`data/queue/` フォルダに `.md` ファイルを追加してコミット＆プッシュするだけで、次の投稿時間に自動投稿されます。

```markdown
---
scheduled: 2026-01-01 08:00
topic: 投稿テーマ
---

ここに投稿本文を書く。
```

---

## ファイル構成

```
threads-automation/
├── threads_api.py      # Threads API との通信処理
├── post.py             # キューから1件取り出して投稿
├── stats.py            # 統計データの自動収集
├── analyze.py          # バズ分析レポートの生成
├── weekly.py           # 日曜夜の週次まとめ実行
├── approve.py          # 生成した投稿をキューに登録
├── requirements.txt    # 必要なパッケージ一覧
├── .env.example        # 環境変数のテンプレート
├── data/
│   ├── queue/          # 投稿待ちファイルを置く場所
│   ├── posted/         # 投稿済みファイルの保管場所
│   ├── posted_log.json # 投稿履歴（自動生成）
│   └── stats.csv       # 統計データ（自動生成）
└── .github/
    └── workflows/
        ├── post.yml    # 自動投稿ワークフロー
        └── stats.yml   # 自動統計収集ワークフロー
```

---

## 週次の運用フロー

```
日曜夜：python3 weekly.py を実行
  ↓
統計収集・バズ分析が自動で走る
  ↓
Claudeへのプロンプトが表示される → コピーしてClaudeに貼る
  ↓
Claudeが21本の投稿文を生成する → approve.py でキューに登録
  ↓
月〜土：何もしない（GitHub Actionsが自動投稿）
```

---

## よくある失敗と対処

| エラー | 原因 | 対処 |
|--------|------|------|
| `This user is not a tester` | Threads テスター招待を承認していない | スマホのThreadsアプリ→設定→アプリとウェブサイト→招待を承認 |
| cronが動かない | JSTとUTCの時差（9時間）の計算ミス | post.yml の cron値を確認 |
| トークンエラー | アクセストークンが期限切れ（60日） | Graph API エクスプローラーで再取得してSecretsを更新 |
| 403 push エラー | GitHub Actions に write 権限がない | stats.yml に `permissions: contents: write` が入っているか確認 |

---

## 注意事項

- アクセストークンの有効期限は **約60日**。期限切れで投稿が止まるので更新を忘れずに
- `data/queue/` が空の場合、投稿はスキップされます（エラーにはなりません）
- `keyword_search` APIは開発モードでは使えません（投稿・統計収集は問題なし）

---

## 作者

**@ronginooth_ai**（ロンギ）
研究歴20年のPhD（生命科学）。エンジニアではない。
ThreadsでAI×研究者の発信効率化について書いています。

このシステムの作り方は Brain の記事で詳しく解説しています。
