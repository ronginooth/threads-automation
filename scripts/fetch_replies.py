"""
コメント取得 & リプライ案生成スクリプト
- 直近25投稿のコメントを取得
- 各コメントに対してClaude APIでリプライ案×3を生成
- docs/replies.html を更新する
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


def generate_reply_drafts(post_text: str, comment_text: str) -> list[str]:
    """Claude APIでリプライ案を3つ生成"""
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    prompt = f"""あなたはThreadsで研究×AIの情報発信をしている研究者です。
研究歴20年以上の視点で、フォロワーからのコメントに丁寧かつ自然に返信してください。

【自分の投稿内容】
{post_text[:300]}

【相手のコメント】
{comment_text}

上記コメントへのリプライ案を3つ考えてください。
- パターン1：共感・感謝ベース（温かみのある返し）
- パターン2：深掘り・追加情報ベース（知的な返し）
- パターン3：会話を広げるベース（次の対話につながる返し）

各案は100〜150文字以内。番号なし。JSON配列で返してください。
["リプライ案1", "リプライ案2", "リプライ案3"]"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )

    text = message.content[0].text.strip()
    # JSONを抽出
    start = text.find("[")
    end = text.rfind("]") + 1
    if start != -1 and end > start:
        return json.loads(text[start:end])
    return [text, "", ""]


def build_html(comment_blocks: list) -> str:
    now_str = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")

    if not comment_blocks:
        body = '<p class="empty">新着コメントはありません</p>'
    else:
        cards = ""
        for block in comment_blocks:
            drafts_html = ""
            for i, draft in enumerate(block["drafts"], 1):
                drafts_html += f"""
                <div class="draft">
                  <span class="draft-label">案{i}</span>
                  <p>{draft}</p>
                </div>"""

            cards += f"""
            <div class="card">
              <div class="post-ref">
                <span class="label">投稿</span>
                <a href="{block['permalink']}" target="_blank">{block['post_text'][:60]}…</a>
              </div>
              <div class="comment-box">
                <span class="username">@{block['username']}</span>
                <p class="comment-text">{block['comment_text']}</p>
                <span class="time">{block['comment_time']}</span>
              </div>
              <div class="drafts-section">
                <p class="drafts-title">リプライ案</p>
                {drafts_html}
              </div>
            </div>"""
        body = cards

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Threads コメント一覧</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, sans-serif;
      background: #f5f5f5;
      padding: 16px;
      max-width: 640px;
      margin: 0 auto;
    }}
    h1 {{ font-size: 18px; margin-bottom: 4px; color: #111; }}
    .updated {{ font-size: 12px; color: #888; margin-bottom: 16px; }}
    .card {{
      background: white;
      border-radius: 12px;
      padding: 16px;
      margin-bottom: 16px;
      box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    }}
    .post-ref {{
      font-size: 12px;
      color: #888;
      margin-bottom: 10px;
      border-left: 3px solid #ddd;
      padding-left: 8px;
    }}
    .post-ref .label {{
      font-weight: bold;
      margin-right: 6px;
    }}
    .post-ref a {{ color: #555; text-decoration: none; }}
    .comment-box {{
      background: #f9f9f9;
      border-radius: 8px;
      padding: 10px 12px;
      margin-bottom: 12px;
    }}
    .username {{ font-weight: bold; font-size: 13px; color: #333; }}
    .comment-text {{ font-size: 14px; color: #222; margin: 4px 0; line-height: 1.5; }}
    .time {{ font-size: 11px; color: #aaa; }}
    .drafts-title {{ font-size: 12px; font-weight: bold; color: #555; margin-bottom: 8px; }}
    .draft {{
      border: 1px solid #e8e8e8;
      border-radius: 8px;
      padding: 10px 12px;
      margin-bottom: 8px;
      cursor: pointer;
      transition: background 0.15s;
    }}
    .draft:active {{ background: #f0f0f0; }}
    .draft-label {{
      font-size: 11px;
      font-weight: bold;
      color: #888;
      display: block;
      margin-bottom: 4px;
    }}
    .draft p {{ font-size: 14px; color: #222; line-height: 1.5; }}
    .empty {{ text-align: center; color: #aaa; padding: 40px 0; font-size: 14px; }}
  </style>
  <script>
    // タップでテキストをクリップボードにコピー
    document.addEventListener('DOMContentLoaded', () => {{
      document.querySelectorAll('.draft').forEach(el => {{
        el.addEventListener('click', () => {{
          const text = el.querySelector('p').textContent;
          navigator.clipboard.writeText(text).then(() => {{
            el.style.background = '#e8f5e9';
            setTimeout(() => el.style.background = '', 800);
          }});
        }});
      }});
    }});
  </script>
</head>
<body>
  <h1>📩 Threads コメント</h1>
  <p class="updated">更新: {now_str}</p>
  {body}
</body>
</html>"""


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

    comment_blocks = []
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

            ts = reply.get("timestamp", "")

            # JSTに変換
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
                drafts = [f"（生成失敗: {e}）", "（手動で入力してください）", ""]

            comment_blocks.append({
                "post_text": post_text,
                "permalink": permalink,
                "username": username,
                "comment_text": comment_text,
                "comment_time": comment_time,
                "drafts": drafts,
            })
            new_seen.add(reply_id)

    DOCS_DIR.mkdir(exist_ok=True)
    html = build_html(comment_blocks)
    (DOCS_DIR / "replies.html").write_text(html, encoding="utf-8")
    print(f"✅ {len(comment_blocks)}件のコメントを更新 → docs/replies.html")

    save_seen(new_seen, ctx.seen_file)


if __name__ == "__main__":
    ctx = get_context()
    run(ctx)
