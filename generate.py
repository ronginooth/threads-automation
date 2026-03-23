"""
投稿文生成スクリプト
config.yml + data/account_profile.md を読んで次週の投稿文を生成する
生成結果は posts/YYYY-MM-DD_week/ に保存（queue には入れない）
レビュー後に approve.py でキューに移動する

前提: python3 prepare.py を先に実行して account_profile.md を生成しておく
"""
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
import yaml
import anthropic
from dotenv import load_dotenv

load_dotenv()

BASE = Path(__file__).parent
REPORT_DIR = BASE / "data"
POSTS_DIR = BASE / "posts"
CONFIG_FILE = BASE / "config.yml"
PROFILE_FILE = BASE / "data" / "account_profile.md"


def get_latest_report() -> str:
    reports = sorted(REPORT_DIR.glob("report_*.md"))
    if not reports:
        return "（分析レポートなし）"
    return reports[-1].read_text(encoding="utf-8")


def get_latest_trends() -> str:
    trends = sorted(REPORT_DIR.glob("trends_*.md"))
    if not trends:
        return "（トレンドレポートなし）"
    return trends[-1].read_text(encoding="utf-8")


def get_next_monday() -> datetime:
    today = datetime.now()
    days_ahead = 7 - today.weekday()
    return today + timedelta(days=days_ahead)


def get_latest_directives() -> str:
    """最新のアナリスト指示書セクションを抽出"""
    report = get_latest_report()
    # レポート内の「アナリスト指示書」セクションを探す
    marker = "## アナリスト指示書"
    idx = report.find(marker)
    if idx != -1:
        # 次の「---」または末尾までを抽出
        end = report.find("---", idx)
        return report[idx:end] if end != -1 else report[idx:]
    return ""


def load_config() -> dict:
    if CONFIG_FILE.exists():
        return yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8"))
    return {}


def load_profile() -> str:
    if PROFILE_FILE.exists():
        return PROFILE_FILE.read_text(encoding="utf-8")
    return ""


def build_time_format(times: list[str]) -> str:
    """config.ymlのtimesから出力フォーマットのサンプルを組み立てる"""
    labels = {0: "朝", 1: "朝", 2: "昼", 3: "夕", 4: "夜"}
    lines = []
    for i, t in enumerate(times):
        label = labels.get(i, "")
        lines.append(f"### Day1-投稿{i+1}（{label}{t}）型: ○○型 | L1\n---\n（投稿文）\n---")
    return "\n\n".join(lines)


def generate_posts() -> str:
    config = load_config()
    profile = load_profile()
    report = get_latest_report()
    trends = get_latest_trends()
    directives = get_latest_directives()
    client = anthropic.Anthropic()

    # configから値を取得（デフォルト付き）
    account = config.get("account", "@ronginooth_ai")
    note_url = config.get("note_url", "")
    max_chars = config.get("max_chars", 200)
    times = config.get("times", ["07:00", "10:00", "13:00", "17:00", "21:00"])
    layers = config.get("layers", {"L1_共感": 21, "L2_教育": 10, "L3_導線": 4})
    posts_per_day = len(times)
    total_posts = posts_per_day * 7

    l1_count = layers.get("L1_共感", 21)
    l2_count = layers.get("L2_教育", 10)
    l3_count = layers.get("L3_導線", 4)

    directives_section = ""
    if directives:
        directives_section = f"""
## アナリスト指示書（前サイクルの分析から導かれた具体的なフィードバック）
{directives}
→ この指示に従って生成すること。特に「伸びているパターン」は優先的に使い、「控える」と書かれたパターンは避けること。
"""

    profile_section = ""
    if profile:
        profile_section = f"""
## アカウントプロフィール（AIが分析した結果）
{profile}
→ このプロフィールのペルソナ・トーン・教育テーマ・導線パターンに従って生成すること。
"""

    time_format = build_time_format(times)

    prompt = f"""あなたはThreads（SNS）の投稿文ライターです。
以下の情報を踏まえて、次の1週間分（7日×{posts_per_day}投稿={total_posts}本）の投稿文を生成してください。
{profile_section}
## バズ分析レポート（自分の過去投稿の実績）
{report}

## トレンドレポート（同ジャンル・他ジャンルのバズ投稿から抽出した新しい型）
{trends}
{directives_section}
## 投稿のルール
- アカウント: {account}
- 1投稿あたり{max_chars}文字以内
- バズった型を優先: 「自分の失敗・本音を先に見せてから質問で終わる」
- トレンドレポートの「次サイクルで試すべき新しい型」を最低3本は取り入れる
- 宣伝型は使わない（「買ってください」「お得」「限定」「セール」等の購買を煽る表現は禁止）
- 各投稿に「型」ラベルをつける（例: あるある型・失敗談型・質問型・二択型・気づき型・教育型・導線型）
- **同じテーマ・同じ構造の投稿が3本以上連続しないように分散させる**
- **過去にバズった投稿と似すぎた内容は避ける（新しい切り口で書く）**

## 投稿の3層構造（重要）
{total_posts}本を以下の3層に分けて生成すること:

### L1（共感・保存）— 週{l1_count}本（{l1_count*100//total_posts}%）
フォロワー増加の主エンジン。
型: あるある型・失敗談型・質問型・二択型・気づき型・びっくり+根拠型

### L2（教育）— 週{l2_count}本（{l2_count*100//total_posts}%）
「この人は知識が深い」と思わせる投稿。有料コンテンツの断片を1つだけ見せる。
→ プロフィールの「L2（教育）テーマリスト」から選ぶこと。
型は「気づき型」「体験談型」をベースにするが、核心には1つの専門的なノウハウを含めること。

### L3（導線）— 週{l3_count}本（{l3_count*100//total_posts}%）
noteの存在を自然に知らせる。体験談・気づきの結末で触れるだけ。
→ プロフィールの「L3（導線）パターン」を参考にすること。
ルール:
- 1日に最大1本（それ以上は宣伝臭くなる）
- 連日で出さない（最低1日空ける）
- 「noteにまとめてます」「noteに書きました」程度の言及に留める
{f'- noteのURL（{note_url}）は入れても入れなくてもよい' if note_url else ''}

## 出力フォーマット
以下のフォーマットで{total_posts}本を出力してください。型の後に「| L1」「| L2」「| L3」のレイヤーラベルを必ず付けること。

{time_format}

（Day1〜Day7まで繰り返し）

## 注意
- 「>狙い:」などのコメントは書かない
- ハッシュタグは不要（あってもなくてもいい）
- 投稿文だけを出力する
- L2/L3投稿でも自然な口調を維持する（講義調にならない）
"""

    print("Claudeが投稿文を生成中...")
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def save_posts(content: str, week_start: datetime):
    week_dir = POSTS_DIR / f"{week_start.strftime('%Y-%m-%d')}_week"
    week_dir.mkdir(parents=True, exist_ok=True)

    # Day1〜Day7ごとに分割して保存
    days = re.split(r"### Day(\d+)-投稿(\d+)", content)

    # 全文も保存
    full_file = week_dir / "all_posts.md"
    full_file.write_text(content, encoding="utf-8")
    print(f"✅ 投稿文を保存: {full_file}")
    print(f"\nレビューして問題なければ以下を実行してください:")
    print(f"  python3 approve.py {week_dir}")

    return week_dir


def run():
    next_monday = get_next_monday()
    print(f"次週（{next_monday.strftime('%Y-%m-%d')}〜）の投稿文を生成します")

    content = generate_posts()
    week_dir = save_posts(content, next_monday)
    print(f"\n生成完了: {week_dir}/all_posts.md を確認してください")


if __name__ == "__main__":
    run()
