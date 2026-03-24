"""
トレンド収集スクリプト
Threads APIのキーワード検索（要上級アクセス）の代わりに
ClaudeのWeb検索ツールを使って同ジャンル・他ジャンルのトレンドを収集する

使い方:
  python3 trends.py --config configs/ronginooth_ai.yml
"""
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import anthropic
from account_context import get_context

load_dotenv()

SAME_GENRE_QUERIES = [
    "Threads 論文 バズ投稿 研究者",
    "Threads AI 論文執筆 フォロワー増加",
    "Threads PhD 大学院 人気投稿",
]
OTHER_GENRE_QUERIES = [
    "Threads 副業 バズ投稿 2026",
    "Threads 習慣化 人気投稿",
    "Threads 育児 仕事 バズった",
]


def collect_trends_via_websearch() -> str:
    """ClaudeのWeb検索ツールでトレンド投稿を収集・分析"""
    client = anthropic.Anthropic()

    queries_text = "\n".join(
        [f"- {q}" for q in SAME_GENRE_QUERIES + OTHER_GENRE_QUERIES]
    )

    prompt = f"""Threadsでバズっている投稿のトレンドを調査してください。

以下の観点で検索・分析をしてください：

## 調査項目
1. **同ジャンル（論文・研究・AI・PhD）**でバズっているThreads投稿の型・構造・フック
2. **他ジャンル（副業・習慣化・育児×仕事・自己啓発）**でバズっているThreads投稿の型・構造・フック
3. 最近（2025〜2026年）のThreadsでよく見られる「バズる投稿の法則」

## 検索ヒント
{queries_text}

## 出力フォーマット
### 同ジャンルのバズ型（3〜5個）
各型について:
- **型名**:
- **構造**:
- **フック例（書き出し）**:
- **なぜバズるか**:

### 他ジャンルから転用できる型（3個）
- **型名**:
- **元ジャンル**:
- **構造**:
- **論文・AI研究への転用案**:

### 次サイクルで試すべき新しい型（3個）
具体的な投稿文の例を1本ずつ書いてください。
"""

    print("ClaudeがWeb検索でトレンドを収集・分析中...")
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=3000,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    )

    # テキスト部分を抽出
    result = ""
    for block in message.content:
        if hasattr(block, "text"):
            result += block.text

    return result


def run(ctx=None):
    if ctx is None:
        ctx = get_context()

    print(f"トレンド収集開始: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    analysis = collect_trends_via_websearch()

    if not analysis:
        print("トレンド収集に失敗しました。")
        return

    # レポート保存
    report_file = ctx.data_dir / f"trends_{datetime.now().strftime('%Y-%m-%d')}.md"
    report_content = f"""# トレンド分析レポート
生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M')}
収集方法: Web検索（Claude）

{analysis}
"""
    report_file.write_text(report_content, encoding="utf-8")

    print(f"\n✅ トレンドレポート保存: {report_file}")
    print(analysis)


if __name__ == "__main__":
    ctx = get_context()
    run(ctx)
