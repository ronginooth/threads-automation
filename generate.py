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
- 宣伝型は使わない（「買ってください」「お得」「限定」「セール」等の購買を煽る表現は禁止）
- 各投稿に「型」ラベルをつける（例: あるある型・失敗談型・質問型・二択型・気づき型・教育型・導線型）
- **同じテーマ・同じ構造の投稿が3本以上連続しないように分散させる**
- **過去にバズった投稿と似すぎた内容は避ける（新しい切り口で書く）**

## 投稿の3層構造（重要）
35本を以下の3層に分けて生成すること:

### L1（共感・保存）— 週21本（60%）
フォロワー増加の主エンジン。既存の型を使う。
型: あるある型・失敗談型・質問型・二択型・気づき型・びっくり+根拠型

### L2（教育）— 週10本（29%）
「この人は知識が深い」と思わせる投稿。noteの有料内容の断片を1つだけ見せる。
以下のテーマから選ぶ:
1. 査読論文は実は28段落に分解できるという事実
2. AIに「構造（設計図）」を渡すことで出力の質が激変すること
3. Introduction/Methods/Results/Discussionそれぞれの書き方のコツ
4. ChatGPTに丸投げしても上手くいかない理由（構造がないから）
5. 文献管理ツール（Zotero）とAIを連携させるメリット
6. 「ゼロから書く」vs「型を埋める作業」の時間差
7. 査読コメントで指摘される典型的な問題と構造化での解決法
型は「気づき型」「体験談型」をベースにするが、核心には1つの専門的なノウハウを含めること。

### L3（導線）— 週4本（11%）
noteの存在を自然に知らせる。体験談・気づきの結末で触れるだけ。
ルール:
- 1日に最大1本（それ以上は宣伝臭くなる）
- 連日で出さない（最低1日空ける）
- 「noteにまとめてます」「noteに書きました」程度の言及に留める
- noteのURL（https://note.com/ronginooth_ai/n/n6e9b15c7eea3）は入れても入れなくてもよい
パターン例:
- 体験談の結末: 「〜の方法、noteに全手順まとめてあります」
- 質問への回答: 「よく聞かれるので、28段落テンプレ+プロンプト集をnoteにまとめました」
- 成果報告: 「このテンプレで書いた論文が通った。noteに設計図を公開してます」

## 出力フォーマット
以下のフォーマットで35本を出力してください。型の後に「| L1」「| L2」「| L3」のレイヤーラベルを必ず付けること。

### Day1-投稿1（朝07:00）型: ○○型 | L1
---
（投稿文）
---

### Day1-投稿2（朝10:00）型: ○○型 | L2
---
（投稿文）
---

### Day1-投稿3（昼13:00）型: ○○型 | L1
---
（投稿文）
---

### Day1-投稿4（夕17:00）型: ○○型 | L1
---
（投稿文）
---

### Day1-投稿5（夜21:00）型: ○○型 | L1
---
（投稿文）
---

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
