"""
トップアカウント発見スクリプト
Claude Web Searchでニッチ別のバズっているThreadsアカウントを自動発見する

使い方:
  python3 discover_accounts.py --config configs/ronginooth_ai.yml
  python3 discover_accounts.py --all   → configs/内の全ニッチを処理
  python3 discover_accounts.py --niche '研究者×AI'

【Claude Codeセッション対応モード】
API呼び出しは行わず、検索リクエストをファイルに保存する。
Claude Code がWebSearchを実行してaccounts.jsonを更新する。
"""
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml
from lib.account_context import AccountContext

BASE = Path(__file__).resolve().parent.parent


def load_accounts(accounts_file) -> dict:
    if accounts_file.exists():
        return json.loads(accounts_file.read_text(encoding="utf-8"))
    return {}


def save_accounts(accounts: dict, buzz_dir, accounts_file):
    buzz_dir.mkdir(parents=True, exist_ok=True)
    accounts_file.write_text(json.dumps(accounts, ensure_ascii=False, indent=2), encoding="utf-8")


def build_discover_request(niche: str, accounts_file: Path) -> str:
    """アカウント発見リクエストを組み立てて返す"""
    return f"""# アカウント発見リクエスト: {niche}
生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M')}
出力先: {accounts_file}

## 調査内容
Threads（Meta社のSNS）で「{niche}」ジャンルのバズっている日本語アカウントを調査してください。

## 検索条件
1. Threadsで実際に投稿しているアカウント
2. エンゲージメント（いいね・リプライ）が多いアカウント
3. フォロワーが多い、または投稿がバズっているアカウント
4. 日本語で発信しているアカウント

## 検索キーワード例
- "Threads {niche} バズ"
- "Threads {niche} 人気アカウント"
- "threads.net {niche}"
- "{niche} SNS 人気"

## 出力フォーマット
以下の形式のJSON配列を作成し、{accounts_file} の "{niche}" キーに追加して保存してください。
既存ファイルが存在する場合は読み込んでマージしてください（重複排除）。

```json
[
  {{
    "username": "Threadsのユーザー名（@なし）",
    "display_name": "表示名",
    "description": "どんな発信をしているか（1文）",
    "followers_estimate": "フォロワー数の推定",
    "source": "どこで見つけたか",
    "discovered_at": "{datetime.now().strftime('%Y-%m-%d')}"
  }}
]
```

最低20アカウント、可能なら50アカウント以上見つけてください。
"""


def get_all_niches() -> list[str]:
    niches = set()
    configs_dir = BASE / "configs"
    if configs_dir.exists():
        for f in configs_dir.glob("*.yml"):
            config = yaml.safe_load(f.read_text(encoding="utf-8"))
            niche = config.get("niche", "")
            if niche:
                niches.add(niche)
    return sorted(niches)


def run(ctx=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", help="設定ファイルのパス")
    parser.add_argument("--all", action="store_true", help="全ニッチを処理")
    parser.add_argument("--niche", help="ニッチを直接指定")
    args, _ = parser.parse_known_args()

    if args.config:
        if ctx is None:
            ctx = AccountContext(args.config)
            ctx.ensure_dirs()
        buzz_dir = ctx.buzz_dir
        accounts_file = buzz_dir / "accounts.json"
        niches = [ctx.niche]
    elif args.all:
        buzz_dir = BASE / "data" / "buzz"
        accounts_file = buzz_dir / "accounts.json"
        niches = get_all_niches()
    elif args.niche:
        buzz_dir = BASE / "data" / "buzz"
        accounts_file = buzz_dir / "accounts.json"
        niches = [args.niche]
    else:
        print("使い方: python3 discover_accounts.py --config configs/xxx.yml")
        return

    buzz_dir.mkdir(parents=True, exist_ok=True)

    for niche in niches:
        print(f"\n🔍 ニッチ: {niche}")
        request = build_discover_request(niche, accounts_file)
        request_file = buzz_dir / f"discover_request_{niche.replace(' ', '_').replace('×', 'x')}.md"
        request_file.write_text(request, encoding="utf-8")
        print(f"  ✅ リクエスト保存: {request_file}")
        print(f"  【Claude Codeセッション対応】")
        print(f"  リクエストを読んでWebSearchを実行し、{accounts_file} を更新してください。")

    print(f"\n{'='*50}")
    print("リクエスト生成完了。Claude Codeで各リクエストを処理してください。")


if __name__ == "__main__":
    run()
