"""
投稿文生成スクリプト
直近の分析レポートを読んでClaudeに次週35本の投稿文を生成させる
生成結果は posts/YYYY-MM-DD_week/ に保存（queue には入れない）
レビュー後に approve.py でキューに移動する
"""
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
import anthropic
from dotenv import load_dotenv

load_dotenv()

REPORT_DIR = Path(__file__).parent / "data"
POSTS_DIR = Path(__file__).parent / "posts"


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


def generate_posts() -> str:
    report = get_latest_report()
    trends = get_latest_trends()
    directives = get_latest_directives()
    client = anthropic.Anthropic()

    directives_section = ""
    if directives:
        directives_section = f"""
## アナリスト指示書（前サイクルの分析から導かれた具体的なフィードバック）
{directives}
→ この指示に従って生成すること。特に「伸びているパターン」は優先的に使い、「控える」と書かれたパターンは避けること。
"""

    prompt = f"""あなたはThreads（SNS）の投稿文ライターです。
以下の「バズ分析レポート」「トレンドレポート」「アナリスト指示書」を踏まえて、次の1週間分（7日×5投稿=35本）の投稿文を生成してください。

## バズ分析レポート（自分の過去投稿の実績）
{report}

## トレンドレポート（同ジャンル・他ジャンルのバズ投稿から抽出した新しい型）
{trends}
{directives_section}
## 投稿のルール
- アカウント: @ronginooth_ai（研究歴20年のPhD、AIを使った論文執筆の効率化を発信）
- 1投稿あたり200文字以内
- バズった型を優先: 「自分の失敗・本音を先に見せてから質問で終わる」
- トレンドレポートの「次サイクルで試すべき新しい型」を最低3本は取り入れる
- 宣伝・自己紹介型は使わない
- 各投稿に「型」ラベルをつける（例: あるある型・失敗談型・質問型・二択型・気づき型）
- **同じテーマ・同じ構造の投稿が3本以上連続しないように分散させる**
- **過去にバズった投稿と似すぎた内容は避ける（新しい切り口で書く）**

## 出力フォーマット
以下のフォーマットで35本を出力してください。

### Day1-投稿1（朝07:00）型: ○○型
---
（投稿文）
---

### Day1-投稿2（朝10:00）型: ○○型
---
（投稿文）
---

### Day1-投稿3（昼13:00）型: ○○型
---
（投稿文）
---

### Day1-投稿4（夕17:00）型: ○○型
---
（投稿文）
---

### Day1-投稿5（夜21:00）型: ○○型
---
（投稿文）
---

（Day1〜Day7まで繰り返し）

## 注意
- 「>狙い:」などのコメントは書かない
- ハッシュタグは不要（あってもなくてもいい）
- 投稿文だけを出力する
"""

    print("Claudeが投稿文を生成中...")
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
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
