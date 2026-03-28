"""
バズ分析スクリプト
data/buzz/accounts.json のアカウント情報をもとに
ClaudeのWeb検索でバズ投稿を検索・分析し、投稿の「型」を抽出する

使い方:
  python3 buzz_analysis.py --config configs/ronginooth_ai.yml
  python3 buzz_analysis.py --all
  python3 buzz_analysis.py --niche '研究者×AI'

【Claude Codeセッション対応モード】
API呼び出しは行わず、分析リクエストをファイルに保存する。
Claude Code がWebSearchを実行してパターンファイルを生成・保存する。
"""
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

BASE = Path(__file__).resolve().parent.parent
BUZZ_DIR = BASE / "data" / "buzz"
ACCOUNTS_FILE = BUZZ_DIR / "accounts.json"
PATTERNS_DIR = BUZZ_DIR / "patterns"


def load_accounts() -> dict:
    if ACCOUNTS_FILE.exists():
        return json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
    return {}


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


def build_analysis_request(niche: str, accounts: list[dict]) -> str:
    """バズ分析リクエストを組み立てて返す"""
    safe_name = niche.replace(" ", "_").replace("/", "_").replace("×", "x")
    output_file = PATTERNS_DIR / f"{safe_name}.md"

    accounts_text = "\n".join(
        f"- @{a.get('username', '?')} ({a.get('display_name', '?')}): {a.get('description', '?')}"
        for a in accounts[:20]
    )

    usernames = [a.get("username", "") for a in accounts[:5] if a.get("username")]
    search_keywords = "\n".join(f'- "threads.net/@{u}" バズ 人気' for u in usernames)

    return f"""# バズ分析リクエスト: {niche}
生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M')}
対象アカウント数: {len(accounts)}
出力先: {output_file}

## 調査対象アカウント
{accounts_text}

## 検索キーワード例
{search_keywords}
- "Threads {niche} バズ投稿"
- "Threads {niche} 人気 投稿"

## 調査内容
1. 各アカウントの最もエンゲージメントが高い投稿（いいね数・リプライ数が多いもの）
2. バズった投稿の具体的な内容・構造
3. どんな書き出し（フック）を使っているか
4. 投稿のフォーマット（リスト形式、質問形式、ストーリー形式など）
5. 文字数の傾向
6. 絵文字や改行の使い方

## 出力フォーマット（このフォーマットで {output_file} に保存してください）
# バズパターン分析: {niche}
更新日: {datetime.now().strftime('%Y-%m-%d')}
分析アカウント数: {len(accounts)}

## 投稿の型 TOP 10
### 1. {{パターン名}}型
- **構造**: このパターンの投稿構造（書き出し→展開→締め）
- **例**: 具体的な投稿例（見つかったものをベースに）
- **なぜ効くか**: エンゲージメントが高い理由
- **文字数目安**: おおよその文字数

（10パターン分）

## トーン分析
- このジャンルで好まれる口調・文体の特徴
- 一人称の使い方
- 敬語 vs タメ口の比率

## エンゲージメントのトリガー
- いいねが増える要素
- リプライが増える要素
- 保存されやすい要素

## フック（書き出し）パターン
- 効果的な1行目のパターンを5つ以上
- 各パターンの例文

## フォーマットの傾向
- 改行の入れ方
- 絵文字の使い方
- 文字数の分布
"""


def analyze_niche(niche: str, accounts_data: dict):
    accounts = accounts_data.get(niche, [])
    if not accounts:
        print(f"  アカウントが見つかりません。先に discover_accounts.py を実行してください。")
        return

    print(f"  対象アカウント数: {len(accounts)}")
    request = build_analysis_request(niche, accounts)

    safe_name = niche.replace(" ", "_").replace("/", "_").replace("×", "x")
    PATTERNS_DIR.mkdir(parents=True, exist_ok=True)
    request_file = BUZZ_DIR / f"analysis_request_{safe_name}.md"
    request_file.write_text(request, encoding="utf-8")

    output_file = PATTERNS_DIR / f"{safe_name}.md"
    print(f"  ✅ リクエスト保存: {request_file}")
    print(f"  【Claude Codeセッション対応】")
    print(f"  リクエストを読んでWebSearchを実行し、{output_file} を保存してください。")


def run():
    parser = argparse.ArgumentParser(description="Threadsバズ投稿の分析")
    parser.add_argument("--config", help="設定ファイルのパス")
    parser.add_argument("--all", action="store_true", help="全ニッチを処理")
    parser.add_argument("--niche", help="ニッチを直接指定")
    args = parser.parse_args()

    if args.all:
        niches = get_all_niches()
    elif args.niche:
        niches = [args.niche]
    elif args.config:
        config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
        niches = [config.get("niche", "general")]
    else:
        print("使い方: python3 buzz_analysis.py --config configs/xxx.yml")
        return

    accounts_data = load_accounts()
    if not accounts_data:
        print("accounts.json が見つかりません。先に discover_accounts.py を実行してください。")
        return

    for niche in niches:
        print(f"\n--- ニッチ: {niche} ---")
        analyze_niche(niche, accounts_data)

    print("\n完了!")


if __name__ == "__main__":
    run()
