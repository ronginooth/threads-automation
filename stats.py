"""
統計収集スクリプト
posted_log.json の投稿を対象にインサイトを取得してCSVに保存する
"""
import json
import csv
from datetime import datetime
from pathlib import Path
from threads_api import get_insights

LOG_FILE = Path(__file__).parent / "data" / "posted_log.json"
STATS_FILE = Path(__file__).parent / "data" / "stats.csv"

HEADERS = ["thread_id", "file", "text_preview", "posted_at", "collected_at",
           "views", "likes", "replies", "reposts", "quotes"]


def load_log() -> list:
    if not LOG_FILE.exists():
        print("posted_log.json がありません。まず投稿してください。")
        return []
    return json.loads(LOG_FILE.read_text())


def load_existing_stats() -> set:
    """すでに記録済みのthread_idセット"""
    if not STATS_FILE.exists():
        return set()
    with open(STATS_FILE, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {row["thread_id"] for row in reader}


def run():
    log = load_log()
    if not log:
        return

    existing = load_existing_stats()
    is_new_file = not STATS_FILE.exists()

    with open(STATS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        if is_new_file:
            writer.writeheader()

        for entry in log:
            thread_id = entry["thread_id"]
            print(f"収集中: {thread_id} ({entry['file']})")
            try:
                insights = get_insights(thread_id)
                row = {
                    "thread_id": thread_id,
                    "file": entry["file"],
                    "text_preview": entry["text"][:50].replace("\n", " "),
                    "posted_at": entry["posted_at"],
                    "collected_at": datetime.now().isoformat(),
                    "views": insights.get("views", 0),
                    "likes": insights.get("likes", 0),
                    "replies": insights.get("replies", 0),
                    "reposts": insights.get("reposts", 0),
                    "quotes": insights.get("quotes", 0),
                }
                writer.writerow(row)
                print(f"  views={row['views']} likes={row['likes']} replies={row['replies']}")
            except Exception as e:
                print(f"  ❌ 取得失敗: {e}")

    print(f"\n✅ stats.csv に保存しました")


if __name__ == "__main__":
    run()
