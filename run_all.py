"""
全アカウント一括実行スクリプト
configs/内の全設定ファイルに対して指定スクリプトを実行する

使い方:
  python3 run_all.py post          # 全アカウント投稿
  python3 run_all.py generate      # 全アカウント投稿生成
  python3 run_all.py weekly        # 全アカウント週次処理
  python3 run_all.py stats         # 全アカウント統計取得
  python3 run_all.py discover      # 全ニッチのアカウント発見
  python3 run_all.py buzz          # 全ニッチのバズ分析
"""
import argparse
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).parent
PYTHON = sys.executable

# コマンド名 → スクリプトファイルの対応
COMMANDS = {
    "post": "post.py",
    "generate": "generate.py",
    "approve": "approve.py",
    "stats": "stats.py",
    "weekly": "weekly.py",
    "prepare": "prepare.py",
    "discover": "discover_accounts.py",
    "buzz": "buzz_analysis.py",
    "dashboard": "dashboard.py",
    "quality": "quality_check.py",
    "fetch": "fetch_replies.py",
    "pivot": "buzz_pivot.py",
}


def find_configs(single: str | None = None) -> list[Path]:
    """設定ファイルを取得する。--config指定時は1件のみ"""
    configs_dir = BASE / "configs"
    if single:
        p = Path(single)
        if not p.exists():
            print(f"エラー: 設定ファイルが見つかりません: {p}")
            sys.exit(1)
        return [p]
    if not configs_dir.exists():
        print(f"エラー: configs/ ディレクトリが見つかりません: {configs_dir}")
        sys.exit(1)
    configs = sorted(configs_dir.glob("*.yml"))
    if not configs:
        print("エラー: configs/ にYMLファイルがありません")
        sys.exit(1)
    return configs


def main():
    parser = argparse.ArgumentParser(description="全アカウント一括実行")
    parser.add_argument("command", choices=list(COMMANDS.keys()),
                        help="実行するコマンド")
    parser.add_argument("--config", default=None,
                        help="単一アカウントのみ実行 (例: configs/ronginooth_ai.yml)")
    args = parser.parse_args()

    script = COMMANDS[args.command]
    script_path = BASE / script
    if not script_path.exists():
        print(f"エラー: スクリプトが見つかりません: {script_path}")
        sys.exit(1)

    configs = find_configs(args.config)

    print("=" * 50)
    print(f"一括実行: {args.command} ({script})")
    print(f"対象: {len(configs)} アカウント")
    print("=" * 50)

    failures = []

    for config_path in configs:
        account_name = config_path.stem
        print(f"\n--- {account_name} ---")

        cmd = [PYTHON, str(script_path), "--config", str(config_path)]
        result = subprocess.run(cmd)

        if result.returncode != 0:
            print(f"  失敗 (exit code: {result.returncode})")
            failures.append(account_name)
        else:
            print(f"  完了")

    # 結果サマリー
    print("\n" + "=" * 50)
    print(f"完了: {len(configs) - len(failures)}/{len(configs)} 成功")
    if failures:
        print(f"失敗: {', '.join(failures)}")
        sys.exit(1)
    print("=" * 50)


if __name__ == "__main__":
    main()
