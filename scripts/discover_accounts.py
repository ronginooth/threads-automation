"""
トップアカウント発見スクリプト
Claude Web Searchでニッチ別のバズっているThreadsアカウントを自動発見する

使い方:
  python3 discover_accounts.py --config configs/ronginooth_ai.yml
  python3 discover_accounts.py --all   → configs/内の全ニッチを処理
  python3 discover_accounts.py --niche '研究者×AI'
"""
import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
import anthropic
import yaml
from lib.account_context import AccountContext

load_dotenv()

BASE = Path(__file__).resolve().parent.parent


def load_accounts(accounts_file) -> dict:
    if accounts_file.exists():
        return json.loads(accounts_file.read_text(encoding="utf-8"))
    return {}


def save_accounts(accounts: dict, buzz_dir, accounts_file):
    buzz_dir.mkdir(parents=True, exist_ok=True)
    accounts_file.write_text(json.dumps(accounts, ensure_ascii=False, indent=2), encoding="utf-8")


def discover_for_niche(niche: str) -> list[dict]:
    """Claude Web Searchでニッチのトップアカウントを発見"""
    client = anthropic.Anthropic()

    prompt = f"""Threads（Meta社のSNS）で「{niche}」ジャンルのバズっている日本語アカウントを調べてください。

以下の条件で検索してください:
1. Threadsで実際に投稿しているアカウント
2. エンゲージメント（いいね・リプライ）が多いアカウント
3. フォロワーが多い、または投稿がバズっているアカウント
4. 日本語で発信しているアカウント

検索キーワード例:
- "Threads {niche} バズ"
- "Threads {niche} 人気アカウント"
- "threads.net {niche}"
- "{niche} SNS 人気"

見つかったアカウントをJSON配列で返してください。各アカウントに以下を含めること:
- username: Threadsのユーザー名（@なし）
- display_name: 表示名
- description: どんな発信をしているか（1文）
- followers_estimate: フォロワー数の推定（わかれば）
- source: どこで見つけたか

最低20アカウント、可能なら50アカウント以上見つけてください。
JSON配列のみを返してください。```json で囲んでください。"""

    print(f"  Claude Web Searchで「{niche}」のアカウントを検索中...")
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 10}],
        messages=[{"role": "user", "content": prompt}],
    )

    # テキストブロックからレスポンスを抽出
    response = ""
    for block in message.content:
        if hasattr(block, "text") and block.text:
            response += block.text
    # JSONを抽出
    start = response.find("[")
    end = response.rfind("]") + 1
    if start != -1 and end > start:
        try:
            accounts = json.loads(response[start:end])
            return accounts
        except json.JSONDecodeError:
            print(f"  ⚠️ JSON解析に失敗しました")
            return []
    return []


def get_all_niches() -> list[str]:
    """configs/内の全ファイルからニッチを収集"""
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

    # buzz_dir と accounts_file を決定
    if args.config:
        if ctx is None:
            ctx = AccountContext(args.config)
            ctx.ensure_dirs()
        buzz_dir = ctx.buzz_dir
        accounts_file = buzz_dir / "accounts.json"
        niches = [ctx.niche]
    elif args.all:
        # 共有のbuzz_dirを使用
        buzz_dir = BASE / "data" / "buzz"
        accounts_file = buzz_dir / "accounts.json"
        niches = get_all_niches()
    elif args.niche:
        buzz_dir = BASE / "data" / "buzz"
        accounts_file = buzz_dir / "accounts.json"
        niches = [args.niche]
    else:
        print("使い方: python3 discover_accounts.py --config configs/xxx.yml")
        print("        python3 discover_accounts.py --all")
        print("        python3 discover_accounts.py --niche '研究者×AI'")
        return

    accounts = load_accounts(accounts_file)
    today = datetime.now().strftime("%Y-%m-%d")

    for niche in niches:
        print(f"\n🔍 ニッチ: {niche}")
        discovered = discover_for_niche(niche)

        if not discovered:
            print(f"  ⚠️ アカウントが見つかりませんでした")
            continue

        # 既存と統合（重複排除）
        existing = {a["username"] for a in accounts.get(niche, [])}
        new_accounts = []
        for acc in discovered:
            if acc.get("username") and acc["username"] not in existing:
                acc["discovered_at"] = today
                new_accounts.append(acc)

        if niche not in accounts:
            accounts[niche] = []
        accounts[niche].extend(new_accounts)

        print(f"  ✅ {len(new_accounts)}件の新規アカウント発見（合計: {len(accounts[niche])}件）")

    save_accounts(accounts, buzz_dir, accounts_file)
    print(f"\n💾 保存: {accounts_file}")


if __name__ == "__main__":
    run()
