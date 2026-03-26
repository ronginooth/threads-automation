# Threads 完全自動化システム

> MacBookを閉じたまま、1日5投稿が出る。リプライの返信案まで自動で届く。
> エンジニアじゃなくても、AIと一緒に作れた仕組みの配布版です。

---

## このシステムでできること

| 機能 | 内容 | 実行場所 |
|------|------|----------|
| **自動投稿** | 毎日 07:00 / 10:00 / 13:00 / 17:00 / 21:00 に Threads へ自動投稿 | GitHub Actions |
| **リプライ取得** | 2時間ごとにコメントを自動取得し、AI返信案を3パターン生成 | GitHub Actions |
| **統計収集** | 毎日 23:00 にインプレッション・いいね・リプライを自動収集 | GitHub Actions |
| **HTMLダッシュボード** | 統計・TOP/BOTTOM分析・キュー管理・返信案を1画面で確認 | GitHub Pages |
| **投稿生成** | 3層構造（共感60%/教育29%/導線11%）で1週間35本を一括生成 | Claude Code |
| **品質チェック** | 生成した投稿を自動で品質チェック・棄却 | Claude Code |
| **バズ分析** | 同ニッチのトップアカウントのバズ投稿パターンを分析 | Claude Code |
| **マルチアカウント** | 設定ファイルを追加するだけで複数アカウント同時運用 | 全体 |

---

## アーキテクチャ

```
┌─────────────────────────────────────────────┐
│  GitHub Actions（自動・24時間稼働）           │
│  ├── post.py      … 15分ごとチェック→投稿    │
│  ├── fetch_replies … 2時間ごとリプ取得+返信案 │
│  ├── stats.py     … 毎日23時に統計収集       │
│  └── dashboard.py … 統計後にHTML更新          │
└───────────────┬─────────────────────────────┘
                │ git push（自動）
                ▼
┌─────────────────────────────────────────────┐
│  GitHub Pages                                │
│  └── docs/dashboard.html（ブラウザで確認）    │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│  Claude Code セッション（週1回・手動）        │
│  ├── generate.py   … 投稿文を一括生成        │
│  ├── quality_check … 品質チェック+棄却        │
│  ├── approve.py    … キューに登録            │
│  ├── analyze.py    … バズ分析レポート         │
│  └── buzz_analysis … トップ投稿のパターン抽出 │
└─────────────────────────────────────────────┘
```

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
| `THREADS_ACCESS_TOKEN_RONGINOOTH_AI` | アカウント固有のアクセストークン |
| `THREADS_USER_ID_RONGINOOTH_AI` | アカウント固有のユーザーID |
| `THREADS_APP_ID` | MetaアプリのID |
| `ANTHROPIC_API_KEY` | Anthropic APIキー（リプライ返信案の生成に使用） |

> 2アカウント目以降は `_ACCOUNT_B` のように接尾辞を変えて追加。

### STEP 4：アカウント設定ファイルを作成

`configs/ronginooth_ai.yml` を参考に、自分のアカウント設定を作成：

```yaml
account: "@your_account"
niche: "あなたのニッチ"
note_url: "https://note.com/your_account/n/xxxxx"
times: ["07:00", "10:00", "13:00", "17:00", "21:00"]
max_chars: 200
layers:
  L1_共感: 21
  L2_教育: 10
  L3_導線: 4
```

### STEP 5：GitHub Actions を有効化

リポジトリの `Actions` タブを開き、ワークフローを有効にする。

自動実行スケジュール：
- **投稿**：15分ごとにチェック → 予定時刻の投稿を実行
- **リプライ取得**：2時間ごと（07:00〜23:00 JST）
- **統計収集 + ダッシュボード更新**：毎日 23:00（JST）

### STEP 6：投稿文を登録する

`data/{アカウント名}/queue/` フォルダに `.md` ファイルを追加してコミット＆プッシュ。

```markdown
---
scheduled: 2026-01-01 08:00
topic: 投稿テーマ
layer: L1_共感
---

ここに投稿本文を書く。
```

---

## ファイル構成

```
threads-automation/
├── run_all.py                  # 全アカウント一括実行
├── requirements.txt
├── .env.example
│
├── configs/                    # アカウント別設定
│   └── ronginooth_ai.yml
│
├── lib/                        # 共有ライブラリ
│   ├── account_context.py      # アカウント設定の読み込み・パス解決
│   └── threads_api.py          # Threads API ラッパー
│
├── scripts/                    # 実行スクリプト
│   ├── post.py                 # キューから投稿（GitHub Actions）
│   ├── stats.py                # 統計収集（GitHub Actions）
│   ├── fetch_replies.py        # リプライ取得+返信案生成（GitHub Actions）
│   ├── dashboard.py            # HTMLダッシュボード生成（GitHub Actions）
│   ├── generate.py             # AI投稿文生成（Claude Code）
│   ├── quality_check.py        # 品質チェック（Claude Code）
│   ├── approve.py              # キュー登録（Claude Code）
│   ├── prepare.py              # 週次準備（Claude Code）
│   ├── analyze.py              # バズ分析レポート（Claude Code）
│   ├── buzz_pivot.py           # バズ展開投稿生成（Claude Code）
│   ├── buzz_analysis.py        # トップ投稿パターン抽出（Claude Code）
│   ├── discover_accounts.py    # トップアカウント発掘（Claude Code）
│   ├── trends.py               # トレンド分析（Claude Code）
│   ├── weekly.py               # 週次バッチ（stats + dashboard）
│   └── scheduler.py            # ローカルスケジューラ
│
├── data/
│   └── ronginooth_ai/          # アカウント別データ
│       ├── queue/              # 投稿待ち
│       ├── posted/             # 投稿済み
│       ├── posted_log.json     # 投稿履歴
│       ├── stats.csv           # 統計データ
│       ├── comments.json       # 取得したコメント
│       └── account_profile.md  # アカウントプロフィール
│
├── docs/                       # GitHub Pages 公開
│   └── dashboard.html          # ダッシュボード（統計・返信案・キュー管理）
│
└── .github/workflows/
    ├── post.yml                # 自動投稿（15分ごと）
    ├── fetch-replies.yml       # リプライ取得（2時間ごと）
    ├── stats.yml               # 統計収集（毎日23時）
    └── buzz-analysis.yml       # バズ分析（手動実行）
```

---

## 週次の運用フロー

```
日曜夜（Claude Code セッション 30分）：
  ① 「来週分お願い」と伝える
     ↓
  ② 統計収集 → バズ分析 → TOP/BOTTOM分析
     ↓
  ③ 35本の投稿文を3層構造で自動生成
     ↓
  ④ 品質チェック → 合格分をキューに登録
     ↓
  ⑤ git push
     ↓
月〜土：何もしない（GitHub Actionsが自動運用）
  - 1日5回、自動投稿
  - 2時間ごと、リプライ取得+返信案生成
  - ダッシュボードで状況確認（スマホからもOK）
  - 返信案をタップしてコピー → Threadsアプリで返信
```

---

## ダッシュボード

GitHub Pages で公開される HTML ダッシュボード（`docs/dashboard.html`）：

- **概要タブ**：キュー残数・累計投稿・平均インプレッション + やることリスト
- **分析タブ**：TOP3 / BOTTOM3 投稿のランキング（スコア付き）
- **キュータブ**：予定投稿一覧（GitHub上で編集・削除可能）
- **返信タブ**：新着コメント + AI返信案3パターン（タップでコピー）

---

## マルチアカウント運用

1. `configs/` に新しいYAMLファイルを追加
2. `data/{アカウント名}/` ディレクトリが自動作成される
3. GitHub Secrets に `_ACCOUNT_B` 接尾辞でトークンを追加
4. ワークフローの matrix に追加：`config: [ronginooth_ai, account_b]`
5. push → 全アカウントが自動運用開始

---

## よくある失敗と対処

| エラー | 原因 | 対処 |
|--------|------|------|
| `This user is not a tester` | Threads テスター招待を承認していない | スマホのThreadsアプリ→設定→アプリとウェブサイト→招待を承認 |
| cronが動かない | JSTとUTCの時差（9時間）の計算ミス | post.yml の cron値を確認 |
| トークンエラー | アクセストークンが期限切れ（60日） | Graph API エクスプローラーで再取得してSecretsを更新 |
| 403 push エラー | GitHub Actions に write 権限がない | ワークフローに `permissions: contents: write` があるか確認 |
| 投稿が出ない | キューが空 / 予定時刻を過ぎている | `data/{アカウント名}/queue/` にファイルがあるか確認 |
| 別アカウントに投稿される | Secret名の接尾辞ミス | `_RONGINOOTH_AI` 等の接尾辞がconfig名と一致しているか確認 |

---

## 注意事項

- アクセストークンの有効期限は **約60日**。期限切れで投稿が止まるので更新を忘れずに
- キューが空の場合、投稿はスキップされます（エラーにはなりません）
- AI投稿生成・品質チェック等はClaude Codeセッション内で実行（API課金なし）
- GitHub Actionsで動くのは Threads API のみ使うスクリプト（post / stats / fetch_replies / dashboard）

---

## 作者

**@ronginooth_ai**（ロンギ）
研究歴20年のPhD（生命科学）。エンジニアではない。
ThreadsでAI×研究者の発信効率化について書いています。

このシステムの作り方は Brain の記事で詳しく解説しています。
