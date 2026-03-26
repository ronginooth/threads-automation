"""
統計収集スクリプト
posted_log.json の投稿を対象にインサイトを取得してCSVに保存する
"""
import json
import csv
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.threads_api import get_insights, get_user_insights
from lib.account_context import get_context

HEADERS = ["thread_id", "file", "text_preview", "posted_at", "collected_at",
           "views", "likes", "replies", "reposts", "quotes"]


def load_log(log_file) -> list:
    if not log_file.exists():
        print("posted_log.json がありません。まず投稿してください。")
        return []
    return json.loads(log_file.read_text())


def load_existing_stats(stats_file) -> set:
    """すでに記録済みのthread_idセット"""
    if not stats_file.exists():
        return set()
    with open(stats_file, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {row["thread_id"] for row in reader}


def run(ctx=None):
    if ctx is None:
        ctx = get_context()

    log = load_log(ctx.log_file)
    if not log:
        return

    existing = load_existing_stats(ctx.stats_file)
    is_new_file = not ctx.stats_file.exists()

    with open(ctx.stats_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        if is_new_file:
            writer.writeheader()

        for entry in log:
            thread_id = entry["thread_id"]
            print(f"収集中: {thread_id} ({entry['file']})")
            try:
                insights = get_insights(thread_id, ctx.token)
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

    # アカウント全体のインサイト（views, clicks, followers等）
    collect_account_insights(ctx)


def collect_account_insights(ctx):
    """ユーザーレベルInsightsを取得してaccount_insights.csvに追記"""
    account_stats_file = ctx.data_dir / "account_insights.csv"
    account_headers = ["collected_at", "views", "clicks", "likes", "replies", "reposts", "quotes", "followers_count"]

    print("\nアカウント全体のインサイトを収集中...")
    try:
        insights = get_user_insights(ctx.token, ctx.user_id)
        row = {
            "collected_at": datetime.now().isoformat(),
            "views": insights.get("views", 0),
            "clicks": insights.get("clicks", 0),
            "likes": insights.get("likes", 0),
            "replies": insights.get("replies", 0),
            "reposts": insights.get("reposts", 0),
            "quotes": insights.get("quotes", 0),
            "followers_count": insights.get("followers_count", 0),
        }

        is_new = not account_stats_file.exists()
        with open(account_stats_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=account_headers)
            if is_new:
                writer.writeheader()
            writer.writerow(row)

        print(f"  views={row['views']} clicks={row['clicks']} followers={row['followers_count']}")
        print(f"✅ account_insights.csv に保存しました")
    except Exception as e:
        print(f"  ⚠️ アカウントInsights取得失敗: {e}")
        print(f"  （フォロワー100人未満の場合、一部メトリクスが利用できない場合があります）")


if __name__ == "__main__":
    ctx = get_context()
    run(ctx)
