"""
ダッシュボード生成スクリプト
全データを1つのHTMLにまとめて docs/dashboard.html に出力する

表示内容:
1. サマリー（今日の投稿数・キュー残数・平均スコア）
2. バズ分析（TOP3 / BOTTOM3）
3. キュー（予定投稿一覧 → GitHubで直接編集可能）
4. 投稿済み（直近の投稿＋統計データ）
5. やることリスト（アクション項目）

GitHub Pagesで公開: https://ronginooth.github.io/threads-automation/dashboard.html
"""
import csv
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.account_context import get_context

BASE = Path(__file__).resolve().parent.parent
DOCS_DIR = BASE / "docs"

GITHUB_REPO = "ronginooth/threads-automation"
GITHUB_EDIT_BASE = f"https://github.com/{GITHUB_REPO}/edit/main"
GITHUB_DELETE_BASE = f"https://github.com/{GITHUB_REPO}/delete/main"

JST = timezone(timedelta(hours=9))


# ========================================
# データ読み込み
# ========================================

def load_queue(queue_dir) -> list[dict]:
    files = sorted(queue_dir.glob("*.md"))
    posts = []
    for f in files:
        content = f.read_text(encoding="utf-8")
        fm = {}
        match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
        if match:
            for line in match.group(1).split("\n"):
                if ":" in line:
                    key, val = line.split(":", 1)
                    fm[key.strip()] = val.strip()
        body = re.sub(r"^---.*?---\s*", "", content, flags=re.DOTALL).strip()
        posts.append({
            "file": f.name,
            "scheduled": fm.get("scheduled", ""),
            "type": fm.get("type", ""),
            "body": body,
        })
    return posts


def load_posted_log(log_file) -> list[dict]:
    if log_file.exists():
        return json.loads(log_file.read_text())
    return []


def load_stats(stats_file) -> list[dict]:
    if not stats_file.exists():
        return []
    with open(stats_file, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_latest_report(data_dir) -> str:
    reports = sorted(data_dir.glob("report_*.md"))
    if reports:
        return reports[-1].read_text(encoding="utf-8")
    return ""


def load_reject_log(reject_log) -> list:
    if reject_log.exists():
        return json.loads(reject_log.read_text())
    return []


def load_comments(data_dir) -> list[dict]:
    f = data_dir / "comments.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return []


def load_account_insights(data_dir) -> list[dict]:
    f = data_dir / "account_insights.csv"
    if not f.exists():
        return []
    with open(f, encoding="utf-8") as fp:
        return list(csv.DictReader(fp))


def score(row: dict) -> float:
    return (
        int(row.get("likes", 0)) * 3
        + int(row.get("replies", 0)) * 5
        + int(row.get("reposts", 0)) * 4
        + int(row.get("quotes", 0)) * 4
        + int(row.get("views", 0)) * 0.1
    )


# ========================================
# HTML生成
# ========================================

def escape(text: str) -> str:
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("\n", "<br>"))


def build_summary_cards(queue, posted_log, stats_rows, kill_switch, account_insights=None) -> str:
    queue_count = len(queue)
    posted_today = 0
    today_str = datetime.now(JST).strftime("%Y-%m-%d")
    for e in posted_log:
        if e.get("posted_at", "")[:10] == today_str:
            posted_today += 1

    total_posted = len(posted_log)
    kill_active = kill_switch.exists()

    # 統計の平均
    avg_views = 0
    avg_likes = 0
    avg_replies = 0
    if stats_rows:
        avg_views = sum(int(r.get("views", 0)) for r in stats_rows) / len(stats_rows)
        avg_likes = sum(int(r.get("likes", 0)) for r in stats_rows) / len(stats_rows)
        avg_replies = sum(int(r.get("replies", 0)) for r in stats_rows) / len(stats_rows)

    # アカウントインサイト（最新）
    followers = 0
    account_views = 0
    if account_insights:
        latest = account_insights[-1]
        followers = int(latest.get("followers_count", 0))
        account_views = int(latest.get("views", 0))

    kill_html = '<div class="stat-card kill">🛑 停止中</div>' if kill_active else ''

    return f"""
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-num">{followers}</div>
        <div class="stat-label">フォロワー</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{account_views:,}</div>
        <div class="stat-label">プロフィール表示</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{queue_count}</div>
        <div class="stat-label">キュー残数</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{posted_today}</div>
        <div class="stat-label">今日の投稿</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{total_posted}</div>
        <div class="stat-label">累計投稿</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{avg_views:.0f}</div>
        <div class="stat-label">平均インプ</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{avg_likes:.1f}</div>
        <div class="stat-label">平均いいね</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{avg_replies:.1f}</div>
        <div class="stat-label">平均リプライ</div>
      </div>
      {kill_html}
    </div>"""


def build_analysis_section(stats_rows) -> str:
    if not stats_rows:
        return '<div class="card"><p class="empty">統計データがまだありません</p></div>'

    for row in stats_rows:
        row["_score"] = score(row)

    sorted_rows = sorted(stats_rows, key=lambda r: r["_score"], reverse=True)
    top3 = sorted_rows[:3]
    bottom3 = sorted_rows[-3:] if len(sorted_rows) >= 6 else []

    cards = ""
    for i, row in enumerate(top3, 1):
        medal = ["🥇", "🥈", "🥉"][i - 1]
        cards += f"""
        <div class="rank-card top">
          <div class="rank-badge">{medal} TOP{i}</div>
          <p class="rank-text">{escape(row.get('text_preview', ''))}</p>
          <div class="rank-metrics">
            <span>👁 {row.get('views', 0)}</span>
            <span>❤️ {row.get('likes', 0)}</span>
            <span>💬 {row.get('replies', 0)}</span>
            <span>🔄 {row.get('reposts', 0)}</span>
            <span class="score">スコア {row['_score']:.0f}</span>
          </div>
        </div>"""

    for i, row in enumerate(bottom3, 1):
        cards += f"""
        <div class="rank-card bottom">
          <div class="rank-badge">⬇️ BOTTOM{i}</div>
          <p class="rank-text">{escape(row.get('text_preview', ''))}</p>
          <div class="rank-metrics">
            <span>👁 {row.get('views', 0)}</span>
            <span>❤️ {row.get('likes', 0)}</span>
            <span>💬 {row.get('replies', 0)}</span>
            <span class="score">スコア {row['_score']:.0f}</span>
          </div>
        </div>"""

    return cards


def build_queue_section(queue) -> str:
    if not queue:
        return '<p class="empty">キューは空です</p>'

    cards = ""
    for post in queue:
        type_class = post["type"].replace(" ", "_").replace("+", "_")
        edit_url = f"{GITHUB_EDIT_BASE}/data/queue/{post['file']}"
        delete_url = f"{GITHUB_DELETE_BASE}/data/queue/{post['file']}"

        cards += f"""
        <div class="queue-card">
          <div class="queue-header">
            <span class="queue-time">{escape(post['scheduled'])}</span>
            <span class="queue-type type-{type_class}">{escape(post['type'])}</span>
          </div>
          <p class="queue-body">{escape(post['body'][:200])}</p>
          <div class="queue-actions">
            <a href="{edit_url}" target="_blank" class="btn btn-edit">✏️ 編集</a>
            <a href="{delete_url}" target="_blank" class="btn btn-delete">🗑 削除</a>
          </div>
        </div>"""

    return cards


def build_posted_section(posted_log, stats_rows) -> str:
    if not posted_log:
        return '<p class="empty">投稿履歴がありません</p>'

    # 統計をthread_idでインデックス化
    stats_map = {}
    for row in stats_rows:
        tid = row.get("thread_id", "")
        if tid:
            existing = stats_map.get(tid)
            if not existing or row.get("collected_at", "") > existing.get("collected_at", ""):
                stats_map[tid] = row

    cards = ""
    for entry in reversed(posted_log[-20:]):
        thread_id = entry.get("thread_id", "")
        text = entry.get("text", "")[:200]
        posted_at = entry.get("posted_at", "")[:16]
        stats = stats_map.get(thread_id, {})

        metrics_html = ""
        if stats:
            s = score(stats)
            metrics_html = f"""
            <div class="posted-metrics">
              <span>👁 {stats.get('views', 0)}</span>
              <span>❤️ {stats.get('likes', 0)}</span>
              <span>💬 {stats.get('replies', 0)}</span>
              <span>🔄 {stats.get('reposts', 0)}</span>
              <span class="score">スコア {s:.0f}</span>
            </div>"""
        else:
            metrics_html = '<div class="posted-metrics"><span class="no-data">統計未取得</span></div>'

        cards += f"""
        <div class="posted-card">
          <div class="posted-time">{posted_at}</div>
          <p class="posted-text">{escape(text)}</p>
          {metrics_html}
        </div>"""

    return cards


def build_actions_section(queue, posted_log, stats_rows, reject_log, kill_switch) -> str:
    items = []

    # キュー残数チェック
    if len(queue) < 5:
        items.append(("🔴", "キュー残数が少ない", f"残り{len(queue)}件。<code>python3 weekly.py</code> で補充してください"))
    elif len(queue) < 10:
        items.append(("🟡", "キュー残数に注意", f"残り{len(queue)}件。今週中に補充を検討"))

    # KILL_SWITCH
    if kill_switch.exists():
        items.append(("🔴", "KILL_SWITCH 有効", f"投稿が停止中です。解除するには <code>{kill_switch}</code> を削除"))

    # 棄却ログ
    if reject_log:
        recent = [r for r in reject_log if r.get("checked_at", "")[:10] == datetime.now(JST).strftime("%Y-%m-%d")]
        if recent:
            items.append(("🟡", f"今日{len(recent)}件が品質チェックで棄却", "rejected_log.json を確認して再生成を検討"))

    # 統計の有無
    if not stats_rows:
        items.append(("🟡", "統計データなし", "まだ投稿後の統計が収集されていません。明日のJST 23:00に自動収集されます"))

    # バズピボットの候補
    if stats_rows:
        for row in stats_rows:
            row["_score"] = score(row)
        top = max(stats_rows, key=lambda r: r["_score"])
        if top["_score"] > 50:
            items.append(("🟢", "バズピボット候補あり", f"スコア{top['_score']:.0f}の投稿から派生生成できます。<code>python3 buzz_pivot.py</code>"))

    if not items:
        items.append(("🟢", "問題なし", "すべて正常に稼働中です"))

    html = ""
    for icon, title, desc in items:
        html += f"""
        <div class="action-item">
          <span class="action-icon">{icon}</span>
          <div>
            <div class="action-title">{title}</div>
            <div class="action-desc">{desc}</div>
          </div>
        </div>"""

    return html


def build_replies_section(comments: list[dict]) -> str:
    unreplied = [c for c in comments if not c.get("replied", False)]
    replied = [c for c in comments if c.get("replied", False)]

    if not unreplied and not replied:
        return '<p class="empty">コメントはありません</p>'

    html = ""

    # 未返信セクション
    if unreplied:
        html += f'<div class="section-subtitle">未返信 ({len(unreplied)}件)</div>'
        for block in unreplied:
            comment_id = block.get("comment_id", "")
            drafts_html = ""
            for i, draft in enumerate(block.get("drafts", []), 1):
                if not draft:
                    continue
                escaped_draft = escape(draft)
                drafts_html += f"""
            <div class="reply-draft" onclick="selectDraft(this, '{comment_id}')">
              <span class="draft-label">案{i}</span>
              <p>{escaped_draft}</p>
            </div>"""

            html += f"""
        <div class="reply-card" id="card-{comment_id}">
          <div class="reply-post-ref">
            <a href="{block['permalink']}" target="_blank">↗ {escape(block['post_text'][:50])}…</a>
          </div>
          <div class="reply-comment">
            <span class="reply-username">@{block['username']}</span>
            <p class="reply-text">{escape(block['comment_text'])}</p>
            <span class="reply-time">{block['comment_time']}</span>
          </div>
          <div class="reply-drafts">
            <p class="drafts-title">💬 案をタップして編集</p>
            {drafts_html}
          </div>
          <div class="reply-editor" id="editor-{comment_id}" style="display:none;">
            <textarea class="reply-textarea" id="textarea-{comment_id}" rows="3" placeholder="返信を入力…"></textarea>
            <div class="reply-actions">
              <button class="btn btn-cancel" onclick="cancelReply('{comment_id}')">キャンセル</button>
              <button class="btn btn-send" onclick="confirmReply('{comment_id}')">返信する</button>
            </div>
          </div>
        </div>"""

    # 返信済みセクション
    if replied:
        html += f'<div class="section-subtitle replied-header">返信済み ({len(replied)}件)</div>'
        for block in replied:
            replied_text = block.get("replied_text", "")
            html += f"""
        <div class="reply-card replied">
          <div class="reply-post-ref">
            <a href="{block['permalink']}" target="_blank">↗ {escape(block['post_text'][:50])}…</a>
          </div>
          <div class="reply-comment">
            <span class="reply-username">@{block['username']}</span>
            <p class="reply-text">{escape(block['comment_text'])}</p>
          </div>
          <div class="replied-badge">✅ 返信済み: {escape(replied_text[:80])}</div>
        </div>"""

    return html


def build_html(ctx) -> str:
    queue = load_queue(ctx.queue_dir)
    posted_log = load_posted_log(ctx.log_file)
    stats_rows = load_stats(ctx.stats_file)
    reject_log = load_reject_log(ctx.reject_log)
    now_str = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")

    account_insights = load_account_insights(ctx.data_dir)
    summary = build_summary_cards(queue, posted_log, stats_rows, ctx.kill_switch, account_insights)
    actions = build_actions_section(queue, posted_log, stats_rows, reject_log, ctx.kill_switch)
    analysis = build_analysis_section(stats_rows)
    queue_html = build_queue_section(queue)
    posted_html = build_posted_section(posted_log, stats_rows)
    comments = load_comments(ctx.data_dir)
    replies_html = build_replies_section(comments)
    unreplied_count = sum(1 for c in comments if not c.get("replied", False))
    replies_badge = f" ({unreplied_count})" if unreplied_count else ""

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Threads Dashboard</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, 'Helvetica Neue', sans-serif;
      background: #0a0a0a;
      color: #e0e0e0;
      min-height: 100vh;
    }}

    /* ===== HEADER ===== */
    .header {{
      background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
      padding: 20px 16px 16px;
      text-align: center;
      border-bottom: 1px solid #222;
    }}
    .header h1 {{
      font-size: 18px;
      font-weight: 700;
      color: #fff;
      margin-bottom: 4px;
    }}
    .header .updated {{
      font-size: 11px;
      color: #666;
    }}

    /* ===== NAV TABS ===== */
    .nav {{
      display: flex;
      background: #111;
      border-bottom: 1px solid #222;
      overflow-x: auto;
      -webkit-overflow-scrolling: touch;
    }}
    .nav-tab {{
      flex: 1;
      min-width: 80px;
      padding: 12px 8px;
      text-align: center;
      font-size: 12px;
      font-weight: 600;
      color: #666;
      border: none;
      background: none;
      cursor: pointer;
      border-bottom: 2px solid transparent;
      white-space: nowrap;
    }}
    .nav-tab.active {{
      color: #4fc3f7;
      border-bottom-color: #4fc3f7;
    }}

    /* ===== SECTIONS ===== */
    .section {{
      display: none;
      padding: 16px;
      max-width: 640px;
      margin: 0 auto;
    }}
    .section.active {{ display: block; }}
    .section-title {{
      font-size: 15px;
      font-weight: 700;
      color: #fff;
      margin-bottom: 12px;
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    /* ===== STATS ROW ===== */
    .stats-row {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 8px;
      margin-bottom: 16px;
    }}
    .stat-card {{
      background: #161616;
      border-radius: 12px;
      padding: 12px 8px;
      text-align: center;
      border: 1px solid #222;
    }}
    .stat-card.kill {{
      background: #2d1111;
      border-color: #c62828;
      color: #ef5350;
      font-weight: 700;
      font-size: 14px;
      grid-column: span 3;
      padding: 16px;
    }}
    .stat-num {{
      font-size: 24px;
      font-weight: 800;
      color: #4fc3f7;
      line-height: 1.1;
    }}
    .stat-label {{
      font-size: 10px;
      color: #666;
      margin-top: 4px;
    }}

    /* ===== ACTION ITEMS ===== */
    .action-item {{
      display: flex;
      gap: 10px;
      align-items: flex-start;
      background: #161616;
      border-radius: 10px;
      padding: 12px;
      margin-bottom: 8px;
      border: 1px solid #222;
    }}
    .action-icon {{ font-size: 18px; flex-shrink: 0; }}
    .action-title {{ font-size: 13px; font-weight: 600; color: #fff; margin-bottom: 2px; }}
    .action-desc {{ font-size: 12px; color: #888; line-height: 1.5; }}
    .action-desc code {{
      background: #222;
      padding: 1px 6px;
      border-radius: 4px;
      font-size: 11px;
      color: #4fc3f7;
    }}

    /* ===== ANALYSIS CARDS ===== */
    .rank-card {{
      background: #161616;
      border-radius: 10px;
      padding: 12px;
      margin-bottom: 8px;
      border: 1px solid #222;
    }}
    .rank-card.top {{ border-left: 3px solid #4caf50; }}
    .rank-card.bottom {{ border-left: 3px solid #ef5350; }}
    .rank-badge {{
      font-size: 12px;
      font-weight: 700;
      margin-bottom: 6px;
    }}
    .rank-text {{
      font-size: 13px;
      color: #ccc;
      line-height: 1.5;
      margin-bottom: 8px;
    }}
    .rank-metrics {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      font-size: 12px;
      color: #888;
    }}
    .rank-metrics .score {{
      color: #4fc3f7;
      font-weight: 700;
    }}

    /* ===== QUEUE ===== */
    .queue-card {{
      background: #161616;
      border-radius: 10px;
      padding: 12px;
      margin-bottom: 8px;
      border: 1px solid #222;
    }}
    .queue-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
    }}
    .queue-time {{
      font-size: 12px;
      color: #4fc3f7;
      font-weight: 600;
    }}
    .queue-type {{
      font-size: 10px;
      font-weight: 700;
      padding: 2px 8px;
      border-radius: 999px;
      background: #222;
      color: #aaa;
    }}
    .queue-body {{
      font-size: 13px;
      color: #ccc;
      line-height: 1.6;
      margin-bottom: 10px;
    }}
    .queue-actions {{
      display: flex;
      gap: 8px;
    }}
    .btn {{
      font-size: 12px;
      font-weight: 600;
      padding: 6px 12px;
      border-radius: 8px;
      text-decoration: none;
      border: 1px solid #333;
      color: #aaa;
      background: #1a1a1a;
    }}
    .btn:active {{ background: #222; }}
    .btn-edit {{ color: #4fc3f7; border-color: #4fc3f7; }}
    .btn-delete {{ color: #ef5350; border-color: #ef5350; }}

    /* ===== POSTED ===== */
    .posted-card {{
      background: #161616;
      border-radius: 10px;
      padding: 12px;
      margin-bottom: 8px;
      border: 1px solid #222;
    }}
    .posted-time {{
      font-size: 11px;
      color: #666;
      margin-bottom: 4px;
    }}
    .posted-text {{
      font-size: 13px;
      color: #ccc;
      line-height: 1.6;
      margin-bottom: 8px;
    }}
    .posted-metrics {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      font-size: 12px;
      color: #888;
    }}
    .posted-metrics .score {{
      color: #4fc3f7;
      font-weight: 700;
    }}
    .posted-metrics .no-data {{
      color: #555;
      font-style: italic;
    }}

    /* ===== COMMON ===== */
    .empty {{
      text-align: center;
      color: #555;
      padding: 40px 0;
      font-size: 13px;
    }}
    .card {{
      background: #161616;
      border-radius: 12px;
      padding: 16px;
      border: 1px solid #222;
    }}

    /* ===== REPLIES ===== */
    .reply-card {{
      background: #161616;
      border-radius: 12px;
      padding: 14px;
      margin-bottom: 12px;
      border: 1px solid #222;
    }}
    .reply-post-ref {{
      font-size: 11px;
      color: #555;
      margin-bottom: 10px;
      padding-left: 8px;
      border-left: 2px solid #333;
    }}
    .reply-post-ref a {{ color: #4fc3f7; text-decoration: none; }}
    .reply-comment {{
      background: #1e1e1e;
      border-radius: 8px;
      padding: 10px 12px;
      margin-bottom: 10px;
    }}
    .reply-username {{ font-size: 12px; font-weight: 700; color: #aaa; }}
    .reply-text {{ font-size: 14px; color: #e0e0e0; margin: 4px 0; line-height: 1.6; }}
    .reply-time {{ font-size: 11px; color: #555; }}
    .drafts-title {{ font-size: 11px; font-weight: 700; color: #666; margin-bottom: 8px; }}
    .reply-draft {{
      border: 1px solid #2a2a2a;
      border-radius: 8px;
      padding: 10px 12px;
      margin-bottom: 6px;
      cursor: pointer;
      transition: background 0.15s, border-color 0.15s;
    }}
    .reply-draft:active, .reply-draft.copied {{ background: #1a2e1a; border-color: #4caf50; }}
    .draft-label {{ font-size: 10px; font-weight: 700; color: #666; display: block; margin-bottom: 4px; }}
    .reply-draft p {{ font-size: 13px; color: #ccc; line-height: 1.5; }}
    .reply-draft.selected {{ background: #1a2e1a; border-color: #4caf50; }}

    /* ===== REPLY EDITOR ===== */
    .reply-editor {{
      margin-top: 10px;
      padding-top: 10px;
      border-top: 1px solid #2a2a2a;
    }}
    .reply-textarea {{
      width: 100%;
      background: #1a1a1a;
      color: #e0e0e0;
      border: 1px solid #333;
      border-radius: 8px;
      padding: 10px 12px;
      font-size: 14px;
      font-family: -apple-system, sans-serif;
      line-height: 1.5;
      resize: vertical;
    }}
    .reply-textarea:focus {{ border-color: #4fc3f7; outline: none; }}
    .reply-actions {{
      display: flex;
      gap: 8px;
      margin-top: 8px;
      justify-content: flex-end;
    }}
    .btn-cancel {{ color: #888; border-color: #444; }}
    .btn-send {{
      color: #fff;
      background: #1976d2;
      border-color: #1976d2;
    }}
    .btn-send:active {{ background: #1565c0; }}
    .btn-sending {{
      background: #555 !important;
      border-color: #555 !important;
      pointer-events: none;
    }}

    /* ===== SECTION SUBTITLE ===== */
    .section-subtitle {{
      font-size: 13px;
      font-weight: 700;
      color: #888;
      margin: 16px 0 8px;
      padding-bottom: 6px;
      border-bottom: 1px solid #222;
    }}
    .replied-header {{ color: #555; }}

    /* ===== REPLIED ===== */
    .reply-card.replied {{
      opacity: 0.5;
    }}
    .replied-badge {{
      font-size: 12px;
      color: #4caf50;
      margin-top: 8px;
      padding: 6px 10px;
      background: #1a2e1a;
      border-radius: 6px;
    }}

    /* ===== CONFIRM MODAL ===== */
    .modal-overlay {{
      display: none;
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0,0,0,0.7);
      z-index: 100;
      justify-content: center;
      align-items: center;
    }}
    .modal-overlay.show {{ display: flex; }}
    .modal {{
      background: #1a1a1a;
      border-radius: 16px;
      padding: 20px;
      max-width: 400px;
      width: 90%;
      border: 1px solid #333;
    }}
    .modal h3 {{ font-size: 16px; color: #fff; margin-bottom: 12px; }}
    .modal .preview {{
      background: #111;
      border-radius: 8px;
      padding: 12px;
      font-size: 14px;
      color: #ccc;
      line-height: 1.5;
      margin-bottom: 16px;
      max-height: 120px;
      overflow-y: auto;
    }}
    .modal-buttons {{
      display: flex;
      gap: 8px;
      justify-content: flex-end;
    }}
    .btn-confirm {{
      color: #fff;
      background: #4caf50;
      border-color: #4caf50;
      font-weight: 700;
    }}

    /* ===== SETUP BANNER ===== */
    .setup-banner {{
      background: #1a1a2e;
      border: 1px solid #4fc3f7;
      border-radius: 10px;
      padding: 12px;
      margin-bottom: 12px;
      font-size: 13px;
      color: #ccc;
    }}
    .setup-banner input {{
      width: 100%;
      background: #111;
      color: #e0e0e0;
      border: 1px solid #333;
      border-radius: 6px;
      padding: 8px;
      margin: 8px 0;
      font-size: 13px;
    }}
    .setup-banner .btn {{ margin-top: 4px; }}

    /* ===== STATUS TOAST ===== */
    .toast {{
      position: fixed;
      bottom: 20px;
      left: 50%;
      transform: translateX(-50%);
      background: #333;
      color: #fff;
      padding: 10px 20px;
      border-radius: 8px;
      font-size: 13px;
      z-index: 200;
      display: none;
    }}
    .toast.show {{ display: block; }}
    .toast.success {{ background: #2e7d32; }}
    .toast.error {{ background: #c62828; }}
  </style>
</head>
<body>

  <div class="header">
    <h1>📊 Threads Dashboard</h1>
    <p class="updated">更新: {now_str}</p>
  </div>

  <nav class="nav">
    <button class="nav-tab active" onclick="showTab('overview')">概要</button>
    <button class="nav-tab" onclick="showTab('analysis')">分析</button>
    <button class="nav-tab" onclick="showTab('queue')">キュー ({len(queue)})</button>
    <button class="nav-tab" onclick="showTab('posted')">投稿済</button>
    <button class="nav-tab" onclick="showTab('replies')">返信{replies_badge}</button>
  </nav>

  <!-- 概要 -->
  <div id="overview" class="section active">
    {summary}
    <div class="section-title">⚡ やること</div>
    {actions}
  </div>

  <!-- 分析 -->
  <div id="analysis" class="section">
    <div class="section-title">📈 バズ分析</div>
    {analysis}
  </div>

  <!-- キュー -->
  <div id="queue" class="section">
    <div class="section-title">📋 投稿キュー</div>
    {queue_html}
  </div>

  <!-- 投稿済み -->
  <div id="posted" class="section">
    <div class="section-title">✅ 投稿済み（直近20件）</div>
    {posted_html}
  </div>

  <!-- 返信 -->
  <div id="replies" class="section">
    <div class="section-title">💬 コメント返信</div>
    <div id="setup-banner" class="setup-banner" style="display:none;">
      ⚙️ 初回設定: GitHub PATを入力するとダッシュボードから直接返信できます
      <input type="password" id="pat-input" placeholder="ghp_xxxx...（fine-grained token / repo scope）">
      <button class="btn btn-edit" onclick="savePAT()">保存</button>
      <span style="font-size:11px;color:#666;"> ブラウザのlocalStorageに保存されます</span>
    </div>
    {replies_html}
  </div>

  <!-- 確認モーダル -->
  <div class="modal-overlay" id="confirm-modal">
    <div class="modal">
      <h3>この内容で返信しますか？</h3>
      <div class="preview" id="modal-preview"></div>
      <div class="modal-buttons">
        <button class="btn btn-cancel" onclick="closeModal()">やめる</button>
        <button class="btn btn-confirm" id="modal-confirm" onclick="sendReply()">返信する</button>
      </div>
    </div>
  </div>

  <!-- ステータス通知 -->
  <div class="toast" id="toast"></div>

  <script>
    const REPO = '{GITHUB_REPO}';
    const CONFIG = 'ronginooth_ai';
    let pendingCommentId = null;

    // --- Tab navigation ---
    function showTab(id) {{
      document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
      document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
      document.getElementById(id).classList.add('active');
      event.target.classList.add('active');
      if (id === 'replies') checkSetup();
    }}

    // --- PAT setup ---
    function checkSetup() {{
      const pat = localStorage.getItem('gh_pat');
      const banner = document.getElementById('setup-banner');
      if (!pat && banner) banner.style.display = 'block';
      else if (banner) banner.style.display = 'none';
    }}
    function savePAT() {{
      const val = document.getElementById('pat-input').value.trim();
      if (val) {{
        localStorage.setItem('gh_pat', val);
        document.getElementById('setup-banner').style.display = 'none';
        showToast('GitHub PAT を保存しました', 'success');
      }}
    }}

    // --- Draft selection ---
    function selectDraft(el, commentId) {{
      const card = document.getElementById('card-' + commentId);
      card.querySelectorAll('.reply-draft').forEach(d => d.classList.remove('selected'));
      el.classList.add('selected');

      const text = el.querySelector('p').textContent;
      const textarea = document.getElementById('textarea-' + commentId);
      textarea.value = text;

      const editor = document.getElementById('editor-' + commentId);
      editor.style.display = 'block';
    }}

    function cancelReply(commentId) {{
      document.getElementById('editor-' + commentId).style.display = 'none';
      const card = document.getElementById('card-' + commentId);
      card.querySelectorAll('.reply-draft').forEach(d => d.classList.remove('selected'));
    }}

    // --- Confirm modal ---
    function confirmReply(commentId) {{
      const text = document.getElementById('textarea-' + commentId).value.trim();
      if (!text) return;

      const pat = localStorage.getItem('gh_pat');
      if (!pat) {{
        showToast('先にGitHub PATを設定してください', 'error');
        checkSetup();
        return;
      }}

      pendingCommentId = commentId;
      document.getElementById('modal-preview').textContent = text;
      document.getElementById('confirm-modal').classList.add('show');
    }}

    function closeModal() {{
      document.getElementById('confirm-modal').classList.remove('show');
      pendingCommentId = null;
    }}

    // --- Send reply via GitHub Actions ---
    async function sendReply() {{
      const commentId = pendingCommentId;
      const text = document.getElementById('textarea-' + commentId).value.trim();
      const pat = localStorage.getItem('gh_pat');

      closeModal();

      const btn = document.querySelector('#editor-' + commentId + ' .btn-send');
      btn.textContent = '送信中…';
      btn.classList.add('btn-sending');

      try {{
        const res = await fetch(
          `https://api.github.com/repos/${{REPO}}/actions/workflows/reply.yml/dispatches`,
          {{
            method: 'POST',
            headers: {{
              'Authorization': `Bearer ${{pat}}`,
              'Accept': 'application/vnd.github.v3+json',
            }},
            body: JSON.stringify({{
              ref: 'main',
              inputs: {{
                config: CONFIG,
                comment_id: commentId,
                reply_text: text,
              }}
            }})
          }}
        );

        if (res.status === 204) {{
          showToast('✅ 返信を送信しました（反映まで1〜2分）', 'success');
          const card = document.getElementById('card-' + commentId);
          card.style.opacity = '0.4';
          btn.textContent = '送信済み ✓';
        }} else if (res.status === 401 || res.status === 403) {{
          showToast('GitHub PATが無効です。再設定してください', 'error');
          localStorage.removeItem('gh_pat');
          checkSetup();
          btn.textContent = '返信する';
          btn.classList.remove('btn-sending');
        }} else {{
          const body = await res.text();
          showToast(`エラー: ${{res.status}} ${{body.slice(0, 100)}}`, 'error');
          btn.textContent = '返信する';
          btn.classList.remove('btn-sending');
        }}
      }} catch (e) {{
        showToast('通信エラー: ' + e.message, 'error');
        btn.textContent = '返信する';
        btn.classList.remove('btn-sending');
      }}
    }}

    // --- Toast ---
    function showToast(msg, type) {{
      const t = document.getElementById('toast');
      t.textContent = msg;
      t.className = 'toast show ' + (type || '');
      setTimeout(() => t.className = 'toast', 3500);
    }}

    // Check setup on load
    document.addEventListener('DOMContentLoaded', checkSetup);
  </script>

</body>
</html>"""


def run(ctx=None):
    if ctx is None:
        ctx = get_context()

    DOCS_DIR.mkdir(exist_ok=True)
    html = build_html(ctx)
    output = DOCS_DIR / "dashboard.html"
    output.write_text(html, encoding="utf-8")
    print(f"✅ ダッシュボード生成: {output}")
    print(f"   https://ronginooth.github.io/threads-automation/dashboard.html")


if __name__ == "__main__":
    ctx = get_context()
    run(ctx)
