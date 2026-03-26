"""
リプライ投稿スクリプト
ダッシュボードから GitHub Actions workflow_dispatch 経由で呼ばれる

使い方:
  python3 scripts/reply.py --config configs/ronginooth_ai.yml \
    --comment-id 12345 --text "返信テキスト"
"""
import json
import argparse
import time
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.account_context import AccountContext
from lib.threads_api import create_reply, publish_post


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--comment-id", required=True, help="返信先のコメントID")
    parser.add_argument("--text", required=True, help="返信テキスト")
    args = parser.parse_args()

    ctx = AccountContext(args.config)
    ctx.ensure_dirs()

    comment_id = args.comment_id
    reply_text = args.text

    print(f"返信先: {comment_id}")
    print(f"返信内容: {reply_text}")

    # Threads APIでリプライ投稿
    creation_id = create_reply(reply_text, comment_id, ctx.token, ctx.user_id)
    print(f"コンテナ作成: {creation_id}")

    time.sleep(2)

    thread_id = publish_post(creation_id, ctx.token, ctx.user_id)
    print(f"✅ リプライ投稿完了: {thread_id}")

    # comments.json の該当コメントを replied: true に更新
    comments_file = ctx.data_dir / "comments.json"
    if comments_file.exists():
        comments = json.loads(comments_file.read_text(encoding="utf-8"))
        for c in comments:
            if c.get("comment_id") == comment_id:
                c["replied"] = True
                c["replied_text"] = reply_text
                c["replied_thread_id"] = thread_id
                break
        comments_file.write_text(json.dumps(comments, ensure_ascii=False, indent=2))
        print(f"✅ comments.json 更新（replied: true）")


if __name__ == "__main__":
    run()
