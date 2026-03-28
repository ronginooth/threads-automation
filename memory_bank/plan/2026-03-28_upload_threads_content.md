# 実装計画：週次自動生成コンテンツ44件のGitHub同期

SNS自動化プロジェクト「Threads Automation」において、AIによって生成された週次コンテンツおよび関連ファイル計44件をGitHubへ正常に同期するための手順。

## 概要

- **目的**: AI生成コンテンツ（投稿案41件、分析ファイル3件、計44件）をGitHubリポジトリへアップロードし、リモートのダッシュボードと同期させる。
- **課題**: `.gitignore` による除外ディレクトリ、および `docs/dashboard.html` のマージ競合。

## 提案される変更

### ターゲットファイルの追加
- `data/ronginooth_ai/queue/` 配下の投稿案（40件の新規追加と既存の調整）
- `data/ronginooth_ai/buzz/` 配下の関連ファイル 3件
- `data/ronginooth_ai/report_2026-03-28.md` を追加し、合計44件とする。
- `scripts/*.py`群の更新および `docs/dashboard.html` を対象に含める。

### 競合解消手順
- `git pull --rebase` を実行。
- `docs/dashboard.html` の競合を手動で解消。
- キューの件数表示（22件）および最新の更新タイムスタンプを維持。

### プッシュ手順
- `git push origin main` を実行。

## 検証プラン

### 自動テスト / 構成確認
- `git status` でコミット済みの状態を確認。
- `git show` で44件のファイルがコミットに含まれていることを確認。

### 手動確認事項
- GitHub上でファイルの反映を確認。
- ダッシュボードの表示整合性を確認。
