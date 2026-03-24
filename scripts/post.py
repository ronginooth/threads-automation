"""
投稿スクリプト
data/queue/ にある .md ファイルを1件取り出してThreadsに投稿する

安全装置:
- KILL_SWITCH: data/KILL_SWITCH ファイルが存在したら全投稿を停止
- 1日の投稿上限: MAX_DAILY_POSTS 件を超えたらその日は停止
- 最低投稿間隔: MIN_INTERVAL_MINUTES 分未満なら投稿しない
"""
import os
import re
import shutil
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

JST = timezone(timedelta(hours=9))
from lib.threads_api import create_post, publish_post
from lib.account_context import get_context

MAX_DAILY_POSTS = 5
MIN_INTERVAL_MINUTES = 60


def load_log(log_file) -> list:
    if log_file.exists():
        return json.loads(log_file.read_text())
    return []


def save_log(log: list, log_file):
    log_file.write_text(json.dumps(log, ensure_ascii=False, indent=2))


def parse_scheduled_time(path: Path):
    """frontmatterのscheduled:フィールドをJSTのdatetimeとして返す。なければNone"""
    content = path.read_text(encoding="utf-8")
    match = re.search(r'^scheduled:\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})', content, re.MULTILINE)
    if match:
        try:
            return datetime.strptime(match.group(1).strip(), "%Y-%m-%d %H:%M").replace(tzinfo=JST)
        except ValueError:
            return None
    return None


def get_next_post(queue_dir) -> Path | None:
    """スケジュール時刻を過ぎた最も古いファイルを返す"""
    now = datetime.now(JST)
    files = sorted(queue_dir.glob("*.md"))
    for f in files:
        scheduled = parse_scheduled_time(f)
        if scheduled is None or scheduled <= now:
            return f
    print(f"投稿時刻未到達のためスキップ（現在 {now.strftime('%H:%M JST')}）")
    return None


def parse_post_file(path: Path) -> str:
    """マークダウンファイルから投稿テキストを抽出（frontmatterを除く）"""
    content = path.read_text(encoding="utf-8")
    # frontmatter（---...---）を除去
    content = re.sub(r"^---.*?---\s*", "", content, flags=re.DOTALL)
    return content.strip()


def check_kill_switch(kill_switch) -> bool:
    """KILL_SWITCHファイルが存在したらTrueを返す"""
    if kill_switch.exists():
        print("🛑 KILL_SWITCH が有効です。全投稿を停止中。")
        print(f"   解除するには {kill_switch} を削除してください。")
        return True
    return False


def check_daily_limit(log_file) -> bool:
    """今日の投稿数が上限を超えていたらTrueを返す"""
    log = load_log(log_file)
    today = datetime.now(JST).strftime("%Y-%m-%d")
    today_count = sum(1 for e in log if e["posted_at"][:10] == today)
    if today_count >= MAX_DAILY_POSTS:
        print(f"⚠️ 本日の投稿上限に達しました（{today_count}/{MAX_DAILY_POSTS}件）")
        return True
    return False


def check_min_interval(log_file) -> bool:
    """前回投稿からの間隔が短すぎたらTrueを返す"""
    log = load_log(log_file)
    if not log:
        return False
    last_posted = log[-1].get("posted_at", "")
    if not last_posted:
        return False
    try:
        last_time = datetime.fromisoformat(last_posted)
        now = datetime.now()
        diff_minutes = (now - last_time).total_seconds() / 60
        if diff_minutes < MIN_INTERVAL_MINUTES:
            print(f"⏳ 前回投稿から{diff_minutes:.0f}分。最低{MIN_INTERVAL_MINUTES}分の間隔が必要です。")
            return True
    except Exception:
        pass
    return False


def run(ctx=None):
    if ctx is None:
        ctx = get_context()

    # 安全チェック
    if check_kill_switch(ctx.kill_switch):
        return
    if check_daily_limit(ctx.log_file):
        return
    if check_min_interval(ctx.log_file):
        return

    post_file = get_next_post(ctx.queue_dir)
    if not post_file:
        print("キューに投稿がありません。")
        return

    text = parse_post_file(post_file)
    if not text:
        print(f"テキストが空です: {post_file.name}")
        return

    print(f"投稿中: {post_file.name}")
    print(f"本文:\n{text}\n")

    try:
        creation_id = create_post(text, ctx.token, ctx.user_id)
        thread_id = publish_post(creation_id, ctx.token, ctx.user_id)
        print(f"✅ 投稿完了 thread_id: {thread_id}")

        # ログに記録
        log = load_log(ctx.log_file)
        log.append({
            "thread_id": thread_id,
            "file": post_file.name,
            "text": text,
            "posted_at": datetime.now().isoformat(),
        })
        save_log(log, ctx.log_file)

        # ファイルをpostedに移動
        dest = ctx.posted_dir / post_file.name
        shutil.move(str(post_file), str(dest))
        print(f"📁 {post_file.name} → posted/")

    except Exception as e:
        print(f"❌ 投稿失敗: {e}")


if __name__ == "__main__":
    ctx = get_context()
    run(ctx)
