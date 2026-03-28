"""
トレンド収集スクリプト
Threads APIのキーワード検索（要上級アクセス）の代わりに
ClaudeのWeb検索ツールを使って同ジャンル・他ジャンルのトレンドを収集する

使い方:
  python3 trends.py --config configs/ronginooth_ai.yml

【Claude Codeセッション対応モード】
API呼び出しは行わず、検索リクエストをファイルに保存する。
Claude Code がWebSearchを実行してトレンドレポートを生成・保存する。
"""
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.account_context import get_context

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


def build_trends_request(ctx) -> str:
    """トレンド収集リクエストを組み立てて返す"""
    queries_text = "\n".join(
        [f"- {q}" for q in SAME_GENRE_QUERIES + OTHER_GENRE_QUERIES]
    )

    output_file = ctx.data_dir / f"trends_{datetime.now().strftime('%Y-%m-%d')}.md"

    return f"""# トレンド収集リクエスト
生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M')}
出力先: {output_file}

## 調査内容
Threadsでバズっている投稿のトレンドを以下のクエリで調査してください。

## 検索クエリ
{queries_text}

## 調査項目
1. **同ジャンル（論文・研究・AI・PhD）**でバズっているThreads投稿の型・構造・フック
2. **他ジャンル（副業・習慣化・育児×仕事・自己啓発）**でバズっているThreads投稿の型・構造・フック
3. 最近（2025〜2026年）のThreadsでよく見られる「バズる投稿の法則」

## 出力フォーマット（このフォーマットで {output_file} に保存してください）
# トレンド分析レポート
生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M')}
収集方法: Web検索（Claude Code）

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


def run(ctx=None):
    if ctx is None:
        ctx = get_context()

    print(f"トレンド収集リクエスト生成: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    request = build_trends_request(ctx)
    request_file = ctx.data_dir / "trends_request.md"
    request_file.write_text(request, encoding="utf-8")

    output_file = ctx.data_dir / f"trends_{datetime.now().strftime('%Y-%m-%d')}.md"

    print(f"✅ リクエスト保存: {request_file}")
    print(f"\n【Claude Codeセッション対応】")
    print(f"リクエストを読んでWebSearchを実行し、トレンドレポートを保存してください:")
    print(f"  request: {request_file}")
    print(f"  output:  {output_file}")


if __name__ == "__main__":
    ctx = get_context()
    run(ctx)
