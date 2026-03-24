"""
バズ分析スクリプト
data/buzz/accounts.json のアカウント情報をもとに
Claude Web Searchでバズ投稿を検索・分析し、投稿の「型」を抽出する

使い方:
  python3 buzz_analysis.py --config configs/ronginooth_ai.yml
  python3 buzz_analysis.py --all
  python3 buzz_analysis.py --niche '研究者×AI'
"""
import os
import json
import argparse
from pathlib import Path
from datetime import datetime
import anthropic
import yaml
from dotenv import load_dotenv

load_dotenv()

BASE = Path(__file__).parent
BUZZ_DIR = BASE / "data" / "buzz"
ACCOUNTS_FILE = BUZZ_DIR / "accounts.json"
PATTERNS_DIR = BUZZ_DIR / "patterns"


def load_accounts() -> dict:
    if ACCOUNTS_FILE.exists():
        return json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
    return {}


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


def batch_accounts(accounts: list[dict], batch_size: int = 5) -> list[list[dict]]:
    """アカウントリストをバッチに分割"""
    return [accounts[i:i + batch_size] for i in range(0, len(accounts), batch_size)]


def search_buzz_posts(client: anthropic.Anthropic, accounts_batch: list[dict], niche: str) -> str:
    """Claude Web Searchでバッチ内アカウントのバズ投稿を検索"""
    usernames = [a.get("username", "") for a in accounts_batch if a.get("username")]
    if not usernames:
        return ""

    accounts_text = "\n".join(
        f"- @{a.get('username', '?')} ({a.get('display_name', '?')}): {a.get('description', '?')}"
        for a in accounts_batch
    )

    prompt = f"""以下のThreadsアカウントのバズっている投稿・人気投稿を調べてください。

ジャンル: {niche}

アカウント一覧:
{accounts_text}

検索してほしいこと:
1. 各アカウントの最もエンゲージメントが高い投稿（いいね数・リプライ数が多いもの）
2. バズった投稿の具体的な内容・構造
3. どんな書き出し（フック）を使っているか
4. 投稿のフォーマット（リスト形式、質問形式、ストーリー形式など）
5. 文字数の傾向
6. 絵文字や改行の使い方

検索キーワード例:
{chr(10).join(f'- "threads.net/@{u}" バズ 人気' for u in usernames[:3])}
- "Threads {niche} バズ投稿"
- "Threads {niche} 人気 投稿"

見つけた情報をできるだけ詳しく報告してください。具体的な投稿内容があればそのまま引用してください。"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 10}],
        messages=[{"role": "user", "content": prompt}],
    )

    # テキストブロックを結合して返す
    texts = []
    for block in message.content:
        if hasattr(block, "text"):
            texts.append(block.text)
    return "\n".join(texts)


def analyze_patterns(client: anthropic.Anthropic, search_results: list[str], niche: str, account_count: int) -> str:
    """収集した検索結果からバズパターンを分析・抽出"""
    combined = "\n\n---\n\n".join(r for r in search_results if r)

    if not combined.strip():
        return ""

    prompt = f"""あなたはSNSマーケティングの専門家です。
以下はThreadsの「{niche}」ジャンルのバズ投稿に関する調査結果です。

この情報を分析し、投稿の「型」（パターン）を抽出してください。

---
{combined}
---

以下のフォーマットで出力してください（Markdown形式）:

# バズパターン分析: {niche}
更新日: {datetime.now().strftime("%Y-%m-%d")}
分析アカウント数: {account_count}

## 投稿の型 TOP 10

各パターンについて以下を書いてください:
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
- 専門用語の使用度合い

## エンゲージメントのトリガー
- いいねが増える要素
- リプライが増える要素
- 保存されやすい要素
- フォローにつながる要素

## フック（書き出し）パターン
- 効果的な1行目のパターンを5つ以上
- 各パターンの例文

## フォーマットの傾向
- 改行の入れ方
- 絵文字の使い方（種類・頻度）
- リスト形式の使い方
- 文字数の分布（短文 vs 長文）

## 投稿タイミング
- バズりやすい時間帯（情報があれば）
- 曜日の傾向（情報があれば）
- 情報が見つからなければ「データなし」と明記

重要:
- 具体的なデータや例を必ず含めること
- 推測の場合は「推測」と明記すること
- generate.pyが投稿生成の参考にできる実用的な内容にすること"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text


def save_patterns(content: str, niche: str):
    """パターン分析結果をファイルに保存"""
    PATTERNS_DIR.mkdir(parents=True, exist_ok=True)
    # ニッチ名をファイル名に使う（スペースや特殊文字を置換）
    safe_name = niche.replace(" ", "_").replace("/", "_").replace("×", "x")
    output_file = PATTERNS_DIR / f"{safe_name}.md"
    output_file.write_text(content, encoding="utf-8")
    return output_file


def analyze_niche(niche: str, accounts_data: dict):
    """1つのニッチのバズ分析を実行"""
    accounts = accounts_data.get(niche, [])
    if not accounts:
        print(f"  アカウントが見つかりません。先に discover_accounts.py を実行してください。")
        return

    print(f"  対象アカウント数: {len(accounts)}")
    client = anthropic.Anthropic()
    batches = batch_accounts(accounts, batch_size=5)
    search_results = []

    for i, batch in enumerate(batches, 1):
        usernames = [a.get("username", "?") for a in batch]
        print(f"  バッチ {i}/{len(batches)} を検索中... ({', '.join(usernames[:3])}{'...' if len(usernames) > 3 else ''})")
        result = search_buzz_posts(client, batch, niche)
        if result:
            search_results.append(result)

    if not search_results:
        print(f"  バズ投稿の情報が見つかりませんでした。")
        return

    print(f"  {len(search_results)}件の検索結果を分析中...")
    analysis = analyze_patterns(client, search_results, niche, len(accounts))

    if not analysis:
        print(f"  分析結果の生成に失敗しました。")
        return

    output_file = save_patterns(analysis, niche)
    print(f"  保存: {output_file}")


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
        print("        python3 buzz_analysis.py --all")
        print("        python3 buzz_analysis.py --niche '研究者×AI'")
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
