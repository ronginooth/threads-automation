"""
週次手動スクリプト
日曜夜に実行する: python3 weekly.py

やること:
1. 統計収集（最新データ更新）
2. バズ分析レポート生成
3. Claudeとのチャットに貼るプロンプトを出力
   → Claude Codeで「次週の投稿生成して」と依頼
4. 生成されたファイルをapprove.pyでキューに登録
"""
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timedelta

BASE = Path(__file__).parent
PYTHON = sys.executable


def run(script: str):
    subprocess.run([PYTHON, str(BASE / script)])


def get_next_monday() -> str:
    today = datetime.now()
    days = 7 - today.weekday()
    return (today + timedelta(days=days)).strftime("%Y-%m-%d")


if __name__ == "__main__":
    print("=" * 50)
    print("週次サイクル開始")
    print("=" * 50)

    print("\n① 統計収集中...")
    run("stats.py")

    print("\n② バズ分析中...")
    run("analyze.py")

    next_monday = get_next_monday()
    report_path = BASE / "data" / f"report_{datetime.now().strftime('%Y-%m-%d')}.md"

    print("\n" + "=" * 50)
    print("③ 以下をClaudeに貼って次週の投稿文を生成してください")
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
