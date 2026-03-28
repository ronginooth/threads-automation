"""
バズ分析スクリプト
stats.csv を読み込んでバズった投稿の型と傾向をレポート出力する
"""
import csv
import json
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.account_context import get_context


def load_stats(stats_file) -> list[dict]:
    if not stats_file.exists():
        print("stats.csv がありません。先に stats.py を実行してください。")
        return []
    with open(stats_file, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    # thread_id の重複を除去（collected_at が最新のものを残す）
    seen: dict[str, dict] = {}
    for row in rows:
        tid = row["thread_id"]
        if tid not in seen or row["collected_at"] > seen[tid]["collected_at"]:
            seen[tid] = row
    return list(seen.values())


def score(row: dict) -> float:
    """エンゲージメントスコアを計算（いいね×3 + リプ×5 + リポスト×4 + インプ×0.1）"""
    return (
        int(row.get("likes", 0)) * 3
        + int(row.get("replies", 0)) * 5
        + int(row.get("reposts", 0)) * 4
        + int(row.get("quotes", 0)) * 4
        + int(row.get("views", 0)) * 0.1
    )


def generate_directives(top3: list, bottom3: list, all_rows: list) -> list[str]:
    """分析結果から次サイクルへの具体的な指示書を生成する"""
    lines = []

    # TOP3の共通パターンを抽出
    if top3:
        top_previews = [r.get("text_preview", "") for r in top3]
        lines.append("### 伸びているパターン（優先して使う）")
        for i, row in enumerate(top3, 1):
            lines.append(f"- TOP{i}: 「{row.get('text_preview', '')}…」"
                        f"（スコア{row['score']:.0f} / リプ{row.get('replies', 0)}）")

        # 1行目の型を分析
        first_lines = []
        for r in top3:
            preview = r.get("text_preview", "")
            if preview:
                first_lines.append(preview.split("。")[0] if "。" in preview else preview[:20])
        if first_lines:
            lines.append(f"- → 1行目の傾向: {', '.join(first_lines)}")
        lines.append("")

    # BOTTOM3の回避パターン
    if bottom3:
        lines.append("### 伸びていないパターン（しばらく控える）")
        for i, row in enumerate(bottom3, 1):
            lines.append(f"- BOTTOM{i}: 「{row.get('text_preview', '')}…」"
                        f"（スコア{row['score']:.0f} / リプ{row.get('replies', 0)}）")
        lines.append("")

    # typeの偏りチェック
    type_counts = {}
    for row in all_rows:
        fname = row.get("file", "")
        # ファイル名からtypeを推定（例: 2026-03-23_1_main.md → main）
        parts = fname.replace(".md", "").split("_")
        if len(parts) >= 3:
            t = parts[-1]
            type_counts[t] = type_counts.get(t, 0) + 1

    if type_counts:
        lines.append("### 投稿タイプのバランス")
        for t, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            lines.append(f"- {t}: {count}件")
        most_common = max(type_counts, key=type_counts.get)
        lines.append(f"- → 「{most_common}」が多め。次サイクルでは他のタイプを増やす")
        lines.append("")

    # リプライが多い投稿の分析
    reply_sorted = sorted(all_rows, key=lambda r: int(r.get("replies", 0)), reverse=True)
    high_reply = [r for r in reply_sorted if int(r.get("replies", 0)) > 0][:3]
    if high_reply:
        lines.append("### リプライが多い投稿（エンゲージメントが高い）")
        for r in high_reply:
            lines.append(f"- 「{r.get('text_preview', '')}…」（リプライ{r.get('replies', 0)}件）")
        lines.append("- → この構造（問いかけ・共感・意見表明を促す型）を優先して使う")
        lines.append("")

    return lines


def run(ctx=None):
    if ctx is None:
        ctx = get_context()

    rows = load_stats(ctx.stats_file)
    if not rows:
        return

    # スコア計算
    for row in rows:
        row["score"] = score(row)

    # スコア降順ソート
    sorted_rows = sorted(rows, key=lambda r: r["score"], reverse=True)

    total = len(rows)
    avg_views = sum(int(r.get("views", 0)) for r in rows) / total
    avg_likes = sum(int(r.get("likes", 0)) for r in rows) / total
    avg_replies = sum(int(r.get("replies", 0)) for r in rows) / total
    top3 = sorted_rows[:3]
    bottom3 = sorted_rows[-3:]

    report_lines = [
        f"# Threads バズ分析レポート",
        f"生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"分析対象: {total}件の投稿",
        "",
        "## 平均パフォーマンス",
        f"- 平均インプレッション: {avg_views:.1f}",
        f"- 平均いいね: {avg_likes:.1f}",
        f"- 平均リプライ: {avg_replies:.1f}",
        "",
        "## バズった投稿 TOP3",
    ]

    for i, row in enumerate(top3, 1):
        report_lines += [
            f"### {i}位（スコア: {row['score']:.1f}）",
            f"**投稿**: {row['text_preview']}...",
            f"- インプ: {row['views']} / いいね: {row['likes']} / リプ: {row['replies']} / リポスト: {row['reposts']}",
            f"- 投稿日時: {row['posted_at']}",
            "",
        ]

    report_lines += [
        "## 伸びなかった投稿 BOTTOM3",
    ]
    for i, row in enumerate(bottom3, 1):
        report_lines += [
            f"### {i}位（スコア: {row['score']:.1f}）",
            f"**投稿**: {row['text_preview']}...",
            f"- インプ: {row['views']} / いいね: {row['likes']} / リプ: {row['replies']}",
            "",
        ]

    # アナリスト指示書を生成
    directives = generate_directives(top3, bottom3, rows)

    report_lines += [
        "## 次サイクルへの示唆",
        "- TOP3の投稿の共通点（書き出しの型・文体・長さ）を次の投稿生成に反映してください",
        "- BOTTOM3の投稿のパターンは避けるか改善を検討してください",
        "",
        "## アナリスト指示書（ライターへの自動フィードバック）",
        "",
        *directives,
        "",
        "---",
        "このレポートをClaudeに渡して「次の週の投稿を生成して」と依頼するとサイクルが回ります。",
    ]

    report = "\n".join(report_lines)
    report_file = ctx.data_dir / f"report_{datetime.now().strftime('%Y-%m-%d')}.md"
    report_file.write_text(report, encoding="utf-8")

    print(report)
    print(f"\n✅ レポートを保存: {report_file}")


if __name__ == "__main__":
    ctx = get_context()
    run(ctx)
