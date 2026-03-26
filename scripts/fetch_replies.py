"""
コメント取得 & リプライ案生成スクリプト
- 直近25投稿のコメントを取得
- 各コメントに対してClaude APIでリプライ案×3を生成
- 未返信のコメントは次回以降も保持する（消えない）
"""
import os
import json
import requests
import anthropic
from datetime import datetime, timezone, timedelta
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from lib.account_context import get_context

load_dotenv()

BASE_URL = "https://graph.threads.net/v1.0"
JST = timezone(timedelta(hours=9))

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs"


def get_my_posts(token: str, user_id: str, limit: int = 25) -> list:
    res = requests.get(
        f"{BASE_URL}/{user_id}/threads",
        params={
            "fields": "id,text,timestamp,permalink",
            "limit": limit,
            "access_token": token,
        },
    )
    res.raise_for_status()
    return res.json().get("data", [])


def get_my_username(token: str) -> str:
    """自分のThreadsユーザー名を取得"""
    res = requests.get(
        f"{BASE_URL}/me",
        params={
            "fields": "username",
            "access_token": token,
        },
    )
    res.raise_for_status()
    return res.json().get("username", "")


def get_replies(post_id: str, token: str) -> list:
    """投稿に対するコメント（リプライ）を取得"""
    res = requests.get(
        f"{BASE_URL}/{post_id}/replies",
        params={
            "fields": "id,text,timestamp,username",
            "access_token": token,
        },
    )
    res.raise_for_status()
    return res.json().get("data", [])


def load_seen(seen_file) -> set:
    if seen_file.exists():
        return set(json.loads(seen_file.read_text()))
    return set()


def save_seen(seen: set, seen_file):
    seen_file.write_text(json.dumps(list(seen), ensure_ascii=False))


def load_existing_comments(data_dir) -> list[dict]:
    """既存のcomments.jsonを読み込む"""
    f = data_dir / "comments.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return []


def generate_reply_drafts(post_text: str, comment_text: str) -> list[str]:
    """Claude APIでリプライ案を3つ生成（短め）"""
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    prompt = f"""あなたはThreadsで研究×AIの情報発信をしている研究者です。
研究歴20年以上の視点で、フォロワーからのコメントに返信してください。

【自分の投稿】
{post_text[:300]}

【相手のコメント】
{comment_text}

リプライ案を3つ。各案50〜80文字。自然な口語で。
JSON配列で返してください。
["案1", "案2", "案3"]"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )

    text = message.content[0].text.strip()
    start = text.find("[")
    end = text.rfind("]") + 1
    if start != -1 and end > start:
        return json.loads(text[start:end])
    return [text, "", ""]


def run(ctx=None):
    if ctx is None:
        ctx = get_context()

    # 自分のユーザー名を取得して自己リプライを除外
    try:
        my_username = get_my_username(ctx.token)
        print(f"自分のユーザー名: @{my_username}")
    except Exception as e:
        print(f"ユーザー名取得エラー: {e}")
        my_username = ""

    seen = load_seen(ctx.seen_file)
    posts = get_my_posts(ctx.token, ctx.user_id, limit=25)

    # 既存コメントを読み込み（未返信のものを保持）
    existing = load_existing_comments(ctx.data_dir)
    existing_ids = {c["comment_id"] for c in existing if "comment_id" in c}

    new_comments = []
    new_seen = set(seen)

    for post in posts:
        post_id = post["id"]
        post_text = post.get("text", "")
        permalink = post.get("permalink", "#")

        try:
            replies = get_replies(post_id, ctx.token)
        except Exception as e:
            print(f"  replies取得エラー {post_id}: {e}")
            continue

        for reply in replies:
            reply_id = reply["id"]
            if reply_id in seen:
                continue

            comment_text = reply.get("text", "")
            username = reply.get("username", "unknown")

            # 自分のリプライはスキップ
            if my_username and username == my_username:
                new_seen.add(reply_id)
                continue

            # 既に処理済みならスキップ
            if reply_id in existing_ids:
                new_seen.add(reply_id)
                continue

            ts = reply.get("timestamp", "")
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(JST)
                comment_time = dt.strftime("%m/%d %H:%M")
            except Exception:
                comment_time = ts

            print(f"新着コメント: @{username} → {comment_text[:40]}")

            try:
                drafts = generate_reply_drafts(post_text, comment_text)
                print(f"  リプライ案生成完了: {len(drafts)}件")
            except Exception as e:
                print(f"  リプライ案生成エラー: {e}")
                drafts = [f"（生成失敗: {e}）", "", ""]

            new_comments.append({
                "comment_id": reply_id,
                "post_id": post_id,
                "post_text": post_text,
                "permalink": permalink,
                "username": username,
                "comment_text": comment_text,
                "comment_time": comment_time,
                "drafts": drafts,
                "replied": False,
            })
            new_seen.add(reply_id)

    # マージ: 未返信の既存コメントを保持 + 新着を追加
    unreplied = [c for c in existing if not c.get("replied", False)]
    # 重複排除（comment_idベース）
    unreplied_ids = {c["comment_id"] for c in unreplied if "comment_id" in c}
    for nc in new_comments:
        if nc["comment_id"] not in unreplied_ids:
            unreplied.append(nc)

    # 返信済みも別途保持（直近20件）
    replied = [c for c in existing if c.get("replied", False)][-20:]

    all_comments = unreplied + replied

    # 保存
    comments_file = ctx.data_dir / "comments.json"
    comments_file.write_text(json.dumps(all_comments, ensure_ascii=False, indent=2))
    print(f"✅ コメント保存: 未返信{len(unreplied)}件 + 返信済{len(replied)}件")

    save_seen(new_seen, ctx.seen_file)


if __name__ == "__main__":
    ctx = get_context()
    run(ctx)
