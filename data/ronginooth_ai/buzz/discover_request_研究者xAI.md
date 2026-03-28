# アカウント発見リクエスト: 研究者×AI
生成日時: 2026-03-28 20:22
出力先: /Users/makino/local-vaults/claude-code-starter-kit/threads-automation/data/ronginooth_ai/buzz/accounts.json

## 調査内容
Threads（Meta社のSNS）で「研究者×AI」ジャンルのバズっている日本語アカウントを調査してください。

## 検索条件
1. Threadsで実際に投稿しているアカウント
2. エンゲージメント（いいね・リプライ）が多いアカウント
3. フォロワーが多い、または投稿がバズっているアカウント
4. 日本語で発信しているアカウント

## 検索キーワード例
- "Threads 研究者×AI バズ"
- "Threads 研究者×AI 人気アカウント"
- "threads.net 研究者×AI"
- "研究者×AI SNS 人気"

## 出力フォーマット
以下の形式のJSON配列を作成し、/Users/makino/local-vaults/claude-code-starter-kit/threads-automation/data/ronginooth_ai/buzz/accounts.json の "研究者×AI" キーに追加して保存してください。
既存ファイルが存在する場合は読み込んでマージしてください（重複排除）。

```json
[
  {
    "username": "Threadsのユーザー名（@なし）",
    "display_name": "表示名",
    "description": "どんな発信をしているか（1文）",
    "followers_estimate": "フォロワー数の推定",
    "source": "どこで見つけたか",
    "discovered_at": "2026-03-28"
  }
]
```

最低20アカウント、可能なら50アカウント以上見つけてください。
