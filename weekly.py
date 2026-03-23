"""
週次手動スクリプト
日曜夜に実行する: python3 weekly.py

やること:
1. 統計収集（最新データ更新）
2. バズ分析レポート生成（アナリスト指示書付き）
3. トレンド収集
4. 投稿文の自動生成（Claude API）
5. 品質チェック（スコア採点 + 類似度 + パターン偏り）
6. 承認待ちとして表示

使い方:
  python3 weekly.py          → 全ステップ実行
  python3 weekly.py --skip-generate  → 生成をスキップ（手動でClaudeに貼る場合）
"""
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timedelta

BASE = Path(__file__).parent
PYTHON = sys.executable


def run(script: str, *args):
    cmd = [PYTHON, str(BASE / script)] + list(args)
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode


def get_next_monday() -> str:
    today = datetime.now()
    days = 7 - today.weekday()
    return (today + timedelta(days=days)).strftime("%Y-%m-%d")


if __name__ == "__main__":
    skip_generate = "--skip-generate" in sys.argv

    print("=" * 50)
    print("週次サイクル開始")
    print("=" * 50)

    print("\n① 統計収集中...")
    run("stats.py")

    print("\n② バズ分析中（アナリスト指示書付き）...")
    run("analyze.py")

    print("\n③ トレンド収集中...")
    run("trends.py")

    next_monday = get_next_monday()

    if skip_generate:
        report_path = BASE / "data" / f"report_{datetime.now().strftime('%Y-%m-%d')}.md"
        print("\n" + "=" * 50)
        print("④ 以下をClaudeに貼って次週の投稿文を生成してください")
        print("=" * 50)
        print(f"""
---コピーここから---
以下の分析レポートを読んで、来週（{next_monday}〜）の
Threads投稿文を7日×3投稿=21本生成してください。

【バズ分析レポート】
{report_path.read_text(encoding="utf-8") if report_path.exists() else "（レポートファイルを確認してください）"}
---コピーここまで---
""")
        print("生成後: python3 approve.py posts/{next_monday}_week")
    else:
        print("\n④ 投稿文を自動生成中（Claude API）...")
        rc = run("generate.py")
        if rc != 0:
            print("❌ 生成に失敗しました。手動で実行してください: python3 generate.py")
        else:
            print("\n⑤ 品質チェック中...")
            week_dir = BASE / "posts" / f"{next_monday}_week"
            if week_dir.exists():
                # approve → queue に入れてからチェック
                print(f"  → approve.py {week_dir}")
                run("approve.py", str(week_dir))

                print("\n  → quality_check.py でキュー内を品質チェック")
                run("quality_check.py")
            else:
                print(f"  ⚠️ {week_dir} が見つかりません。generate.pyの出力を確認してください。")

    print("\n" + "=" * 50)
    print("週次サイクル完了")
    print("=" * 50)
