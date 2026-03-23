"""
バズピボット
スコア上位の投稿から派生投稿を3本自動生成し、品質チェック後にキューに登録する

使い方:
  python3 buzz_pivot.py              → 最新のstats.csvからTOP1を検出して派生生成
  python3 buzz_pivot.py --top 3      → TOP3それぞれから派生生成（計9本）
  python3 buzz_pivot.py --text "..." → 指定テキストから派生生成
"""
import os
import sys
import re
import csv
import json
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
import anthropic

load_dotenv()

BASE = Path(__file__).parent
STATS_FILE = BASE / "data" / "stats.csv"
QUEUE_DIR = BASE / "data" / "queue"
PIVOT_LOG = BASE / "data" / "pivot_log.json"

PIVOT_COUNT = 3  # 1つのバズ投稿から生成する派生数


def load_stats() -> list[dict]:
    if not STATS_FILE.exists():
        return []
    with open(STATS_FILE, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def score(row: dict) -> float:
    return (
        int(row.get("likes", 0)) * 3
        + int(row.get("replies", 0)) * 5
        + int(row.get("reposts", 0)) * 4
        + int(row.get("quotes", 0)) * 4
        + int(row.get("views", 0)) * 0.1
    )


def get_top_posts(n: int = 1) -> list[dict]:
    """スコア上位n件の投稿を返す"""
    rows = load_stats()
    if not rows:
        print("stats.csv がありません。先に stats.py を実行してください。")
        return []
    for row in rows:
        row["score"] = score(row)
    sorted_rows = sorted(rows, key=lambda r: r["score"], reverse=True)

    # 既にピボット済みの投稿を除外
    pivoted = load_pivot_log()
    pivoted_ids = {p["source_thread_id"] for p in pivoted}

    candidates = [r for r in sorted_rows if r["thread_id"] not in pivoted_ids]
    return candidates[:n]


def generate_pivot_posts(original_text: str) -> list[dict]:
    """バズ投稿から派生投稿を3本生成"""
    client = anthropic.Anthropic()

    prompt = f"""以下のThreads投稿がバズりました。この投稿から派生する新しい投稿を{PIVOT_COUNT}本生成してください。

【バズった投稿】
{original_text}

## 派生の方針
元の投稿と「関連するが別の切り口」で書いてください。具体的には：
1. **深掘り型**: 元の投稿で触れた事実を掘り下げる（「じゃあ残りの○○%は？」「なぜそうなるのか？」）
2. **反転型**: 元の投稿の逆の立場や別の視点で書く（「一方で○○という研究もある」）
3. **実践型**: 元の投稿の知見を「具体的にどうすればいいか」に変換する（「だからこうする」）

## ルール
- アカウント: @ronginooth_ai（研究歴20年のPhD、研究×AIの発信）
- 1投稿200文字以内
- 元の投稿のコピーや言い換えはNG（新しい情報を入れる）
- AI臭い表現は使わない

## 出力フォーマット
JSON配列で返してください。
[
  {{"type": "深掘り", "text": "投稿文1"}},
  {{"type": "反転", "text": "投稿文2"}},
  {{"type": "実践", "text": "投稿文3"}}
]"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text.strip()
    start = response_text.find("[")
    end = response_text.rfind("]") + 1
    if start != -1 and end > start:
        return json.loads(response_text[start:end])
    raise ValueError(f"派生投稿の解析に失敗: {response_text}")


def save_to_queue(posts: list[dict], source_text: str) -> list[str]:
    """派生投稿をキューに保存"""
    saved = []
    now = datetime.now()

    for i, post in enumerate(posts):
        # 翌日以降にスケジュール（既存キューと被らないように）
        scheduled_date = now + timedelta(days=i + 1)
        # 空いている時間帯を使う（14:00をピボット枠にする）
        scheduled_time = "14:00"
        scheduled_str = f"{scheduled_date.strftime('%Y-%m-%d')} {scheduled_time}"

        pivot_type = post.get("type", "派生")
        text = post.get("text", "")

        filename = f"{scheduled_date.strftime('%Y-%m-%d')}_pivot_{pivot_type}.md"
        filepath = QUEUE_DIR / filename

        content = f"""---
type: pivot_{pivot_type}
scheduled: {scheduled_str}
source: "{source_text[:40]}..."
---

{text}
"""
        filepath.write_text(content, encoding="utf-8")
        saved.append(filename)
        print(f"  ✅ {filename}")

    return saved


def load_pivot_log() -> list:
    if PIVOT_LOG.exists():
        return json.loads(PIVOT_LOG.read_text())
    return []


def save_pivot_log(log: list):
    PIVOT_LOG.write_text(json.dumps(log, ensure_ascii=False, indent=2))


def run_quality_check():
    """品質チェックを実行（importして直接呼ぶ）"""
    try:
        from quality_check import check_queue
        print("\n品質チェック中...")
        check_queue()
    except Exception as e:
        print(f"品質チェックエラー: {e}")


def run():
    # 引数解析
    top_n = 1
    manual_text = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--top" and i + 1 < len(args):
            top_n = int(args[i + 1])
            i += 2
        elif args[i] == "--text" and i + 1 < len(args):
            manual_text = args[i + 1]
            i += 2
        else:
            i += 1

    pivot_log = load_pivot_log()

    if manual_text:
        # 手動指定テキストから派生
        print(f"指定テキストから派生投稿を生成します")
        print(f"  元: {manual_text[:60]}…")
        posts = generate_pivot_posts(manual_text)
        saved = save_to_queue(posts, manual_text)
        pivot_log.append({
            "source_thread_id": "manual",
            "source_text": manual_text[:100],
            "generated_at": datetime.now().isoformat(),
            "files": saved,
        })
    else:
        # stats.csvからTOP投稿を検出
        top_posts = get_top_posts(top_n)
        if not top_posts:
            print("バズピボットの対象となる投稿がありません。")
            return

        for rank, post in enumerate(top_posts, 1):
            source_text = post.get("text_preview", "")
            thread_id = post["thread_id"]
            print(f"\n{'='*50}")
            print(f"TOP{rank}（スコア: {post['score']:.0f}）")
            print(f"  元: {source_text}…")
            print(f"  → 派生{PIVOT_COUNT}本を生成中...")

            # posted_log.jsonから全文を取得
            full_text = source_text
            log_file = BASE / "data" / "posted_log.json"
            if log_file.exists():
                log = json.loads(log_file.read_text())
                for entry in log:
                    if entry.get("thread_id") == thread_id:
                        full_text = entry.get("text", source_text)
                        break

            try:
                posts = generate_pivot_posts(full_text)
                saved = save_to_queue(posts, full_text)
                pivot_log.append({
                    "source_thread_id": thread_id,
                    "source_text": full_text[:100],
                    "source_score": post["score"],
                    "generated_at": datetime.now().isoformat(),
                    "files": saved,
                })
                print(f"  → {len(saved)}本をキューに登録")
            except Exception as e:
                print(f"  ❌ 生成失敗: {e}")

    save_pivot_log(pivot_log)

    # 品質チェック
    run_quality_check()

    print(f"\n{'='*50}")
    print("バズピボット完了")
    print(f"  pivot_log.json に記録済み")


if __name__ == "__main__":
    run()
