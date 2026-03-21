"""
投稿スクリプト
data/queue/ にある .md ファイルを1件取り出してThreadsに投稿する
"""
import os
import re
import shutil
import json
from datetime import datetime
from pathlib import Path
from threads_api import create_post, publish_post

QUEUE_DIR = Path(__file__).parent / "data" / "queue"
POSTED_DIR = Path(__file__).parent / "data" / "posted"
LOG_FILE = Path(__file__).parent / "data" / "posted_log.json"


def load_log() -> list:
    if LOG_FILE.exists():
        return json.loads(LOG_FILE.read_text())
    return []


def save_log(log: list):
    LOG_FILE.write_text(json.dumps(log, ensure_ascii=False, indent=2))


def get_next_post() -> Path | None:
    """キューから最も古いファイルを返す"""
    files = sorted(QUEUE_DIR.glob("*.md"))
    return files[0] if files else None


def parse_post_file(path: Path) -> str:
    """マークダウンファイルから投稿テキストを抽出（frontmatterを除く）"""
    content = path.read_text(encoding="utf-8")
    # frontmatter（---...---）を除去
    content = re.sub(r"^---.*?---\s*", "", content, flags=re.DOTALL)
    return content.strip()


def run():
    post_file = get_next_post()
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
        creation_id = create_post(text)
        thread_id = publish_post(creation_id)
        print(f"✅ 投稿完了 thread_id: {thread_id}")

        # ログに記録
        log = load_log()
        log.append({
            "thread_id": thread_id,
            "file": post_file.name,
            "text": text,
            "posted_at": datetime.now().isoformat(),
        })
        save_log(log)

        # ファイルをpostedに移動
        dest = POSTED_DIR / post_file.name
        shutil.move(str(post_file), str(dest))
        print(f"📁 {post_file.name} → posted/")

    except Exception as e:
        print(f"❌ 投稿失敗: {e}")


if __name__ == "__main__":
    run()
