"""
週次スクリプト（Threads APIのみ）
統計収集とダッシュボード更新を実行する

Anthropic APIを使う作業（投稿生成・品質チェック・トレンド分析等）は
Claude Codeセッション内で手動実行する

使い方:
  python3 weekly.py --config configs/ronginooth_ai.yml
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
    # --config 引数を取得
    config_path = None
    for i, arg in enumerate(sys.argv):
        if arg == "--config" and i + 1 < len(sys.argv):
            config_path = sys.argv[i + 1]
    if not config_path:
        print("使い方: python3 weekly.py --config configs/ronginooth_ai.yml")
        sys.exit(1)

    print("=" * 50)
    print(f"週次サイクル開始: {config_path}")
    print("=" * 50)

    print("\n① 統計収集中...")
    run("scripts/stats.py", config_path)

    print("\n② ダッシュボード更新中...")
    run("scripts/dashboard.py", config_path)

    print("\n" + "=" * 50)
    print("週次サイクル完了")
    print("")
    print("以下はClaude Codeセッション内で実行してください:")
    print("  - 投稿生成・品質チェック・承認")
    print("  - トレンド収集・バズ分析")
    print("  - プロフィール更新")
    print("=" * 50)
