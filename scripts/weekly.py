"""
週次スクリプト（Threads APIのみ自動実行）
統計収集とダッシュボード更新を実行する

使い方:
  python3 weekly.py --config configs/ronginooth_ai.yml

【完全な週次サイクルの流れ】

=== 自動実行（このスクリプト） ===
① stats.py         → 統計収集
② dashboard.py     → ダッシュボード更新

=== Claude Codeセッションで実行 ===
③ analyze.py       → バズ分析レポート生成（data/report_*.md）
④ prepare.py       → アカウントプロフィール更新（初回 or --force 時のみ）
   └─ Claude Code: prepare_prompt.md を読んで account_profile.md を保存
⑤ discover_accounts.py → 競合アカウント発見（月次推奨）
   └─ Claude Code: discover_request_*.md を読んでWebSearch → accounts.json を更新
⑥ buzz_analysis.py → バズパターン分析
   └─ Claude Code: analysis_request_*.md を読んでWebSearch → patterns/*.md を保存
⑦ trends.py        → トレンド収集
   └─ Claude Code: trends_request.md を読んでWebSearch → trends_*.md を保存
⑧ buzz_pivot.py    → バズ投稿の派生生成
   └─ Claude Code: pivot_prompt_*.md を読んで派生JSON生成
   └─ python3 buzz_pivot.py --apply pivot_response_*.json
⑨ generate.py      → 投稿生成プロンプト作成
   └─ Claude Code: prompt.md を読んで all_posts.md を生成
⑩ quality_check.py → 品質チェック
   └─ Claude Code: quality_request.md を読んで quality_response.json を生成
   └─ python3 quality_check.py --apply quality_response.json
⑪ approve.py       → キューに登録
"""
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
PYTHON = sys.executable


def run(script: str, config_path: str, *args):
    cmd = [PYTHON, str(BASE / script), "--config", config_path] + list(args)
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode


if __name__ == "__main__":
    config_path = None
    for i, arg in enumerate(sys.argv):
        if arg == "--config" and i + 1 < len(sys.argv):
            config_path = sys.argv[i + 1]
    if not config_path:
        print("使い方: python3 weekly.py --config configs/ronginooth_ai.yml")
        sys.exit(1)

    print("=" * 60)
    print(f"週次サイクル開始: {config_path}")
    print("=" * 60)

    print("\n【自動実行】")
    print("\n① 統計収集中...")
    run("scripts/stats.py", config_path)

    print("\n② ダッシュボード更新中...")
    run("scripts/dashboard.py", config_path)

    print("\n" + "=" * 60)
    print("自動実行ステップ完了")
    print("=" * 60)

    print("""
【Claude Codeセッションで順番に実行してください】

③ analyze.py — バズ分析レポート生成
   python3 scripts/analyze.py --config {config}

④ prepare.py — アカウントプロフィール更新（変更がある場合のみ）
   python3 scripts/prepare.py --config {config} --force
   → Claude Code: prepare_prompt.md を読んで account_profile.md を保存

⑤ discover_accounts.py — 競合アカウント発見（月次）
   python3 scripts/discover_accounts.py --config {config}
   → Claude Code: discover_request_*.md を読んでWebSearch → accounts.json 更新

⑥ buzz_analysis.py — バズパターン分析
   python3 scripts/buzz_analysis.py --config {config}
   → Claude Code: analysis_request_*.md を読んでWebSearch → patterns/*.md 保存

⑦ trends.py — トレンド収集
   python3 scripts/trends.py --config {config}
   → Claude Code: trends_request.md を読んでWebSearch → trends_*.md 保存

⑧ buzz_pivot.py — バズ投稿の派生生成
   python3 scripts/buzz_pivot.py --config {config} --top 3
   → Claude Code: pivot_prompt_*.md を読んでJSON生成 → pivot_response_*.json に保存
   → python3 scripts/buzz_pivot.py --config {config} --apply <response.json>

⑨ generate.py — 投稿文生成
   python3 scripts/generate.py --config {config}
   → Claude Code: prompt.md を読んで all_posts.md を生成

⑩ quality_check.py — 品質チェック
   python3 scripts/quality_check.py --config {config}
   → Claude Code: quality_request.md を読んで quality_response.json を生成
   → python3 scripts/quality_check.py --config {config} --apply <response.json>

⑪ approve.py — キューに登録
   python3 scripts/approve.py --config {config} posts/<week_dir>
""".format(config=config_path))
