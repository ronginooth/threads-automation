"""
バズピボット
スコア上位の投稿から派生投稿を3本自動生成し、品質チェック後にキューに登録する

使い方:
  python3 buzz_pivot.py              → 最新のstats.csvからTOP1を検出して派生生成
  python3 buzz_pivot.py --top 3      → TOP3それぞれから派生生成（計9本）
  python3 buzz_pivot.py --text "..." → 指定テキストから派生生成
  python3 buzz_pivot.py --apply <response.json> → Claude Codeが生成したJSONをキューに登録

【Claude Codeセッション対応モード】
API呼び出しは行わず、プロンプトをファイルに保存する。
Claude Code がプロンプトを読んで派生投稿JSONを生成し、--apply で登録する。
"""
import sys
import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.account_context import get_context

PIVOT_COUNT = 3  # 1つのバズ投稿から生成する派生数


def load_stats(stats_file) -> list[dict]:
    if not stats_file.exists():
        return []
    with open(stats_file, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def score(row: dict) -> float:
    return (
        int(row.get("likes", 0)) * 3
        + int(row.get("replies", 0)) * 5
        + int(row.get("reposts", 0)) * 4
        + int(row.get("quotes", 0)) * 4
        + int(row.get("views", 0)) * 0.1
    )


def get_top_posts(stats_file, pivot_log_file, n: int = 1) -> list[dict]:
    """スコア上位n件の投稿を返す"""
    rows = load_stats(stats_file)
    if not rows:
        print("stats.csv がありません。先に stats.py を実行してください。")
        return []
    for row in rows:
        row["score"] = score(row)
    sorted_rows = sorted(rows, key=lambda r: r["score"], reverse=True)

    # 既にピボット済みの投稿を除外
    pivoted = load_pivot_log(pivot_log_file)
    pivoted_ids = {p["source_thread_id"] for p in pivoted}

    candidates = [r for r in sorted_rows if r["thread_id"] not in pivoted_ids]
    return candidates[:n]


def build_pivot_prompt(original_text: str) -> str:
    """派生投稿生成プロンプトを組み立てて返す（API呼び出しなし）"""
    return f"""以下のThreads投稿がバズりました。この投稿から派生する新しい投稿を{PIVOT_COUNT}本生成してください。

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
JSON配列のみ返してください（他のテキスト不要）。
[
  {{"type": "深掘り", "text": "投稿文1"}},
  {{"type": "反転", "text": "投稿文2"}},
  {{"type": "実践", "text": "投稿文3"}}
]"""


def save_to_queue(posts: list[dict], source_text: str, queue_dir) -> list[str]:
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
        filepath = queue_dir / filename

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


def load_pivot_log(pivot_log_file) -> list:
    if pivot_log_file.exists():
        return json.loads(pivot_log_file.read_text())
    return []


def save_pivot_log(log: list, pivot_log_file):
    pivot_log_file.write_text(json.dumps(log, ensure_ascii=False, indent=2))


def run_quality_check():
    """品質チェックを実行（importして直接呼ぶ）"""
    try:
        from scripts.quality_check import check_queue
        print("\n品質チェック中...")
        check_queue()
    except Exception as e:
        print(f"品質チェックエラー: {e}")


def apply_pivot_response(response_file: Path, source_text: str, ctx) -> list[str]:
    """Claude Codeが生成したJSONを読んでキューに登録する"""
    posts = json.loads(response_file.read_text(encoding="utf-8"))
    saved = save_to_queue(posts, source_text, ctx.queue_dir)

    pivot_log = load_pivot_log(ctx.pivot_log)
    pivot_log.append({
        "source_thread_id": "claude_code",
        "source_text": source_text[:100],
        "generated_at": datetime.now().isoformat(),
        "files": saved,
        "response_file": str(response_file),
    })
    save_pivot_log(pivot_log, ctx.pivot_log)
    print(f"\n{len(saved)}本をキューに登録しました。")
    return saved


def run(ctx=None):
    if ctx is None:
        ctx = get_context()

    # 引数解析
    top_n = 1
    manual_text = None
    apply_file = None
    apply_source = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--top" and i + 1 < len(args):
            top_n = int(args[i + 1])
            i += 2
        elif args[i] == "--text" and i + 1 < len(args):
            manual_text = args[i + 1]
            i += 2
        elif args[i] == "--apply" and i + 1 < len(args):
            apply_file = Path(args[i + 1])
            i += 2
        elif args[i] == "--source" and i + 1 < len(args):
            apply_source = args[i + 1]
            i += 2
        elif args[i] == "--config" and i + 1 < len(args):
            i += 2
        else:
            i += 1

    # --apply モード: Claude Codeが生成したJSONをキューに登録
    if apply_file:
        if not apply_file.exists():
            print(f"ファイルが見つかりません: {apply_file}")
            return
        apply_pivot_response(apply_file, apply_source or "", ctx)
        return

    buzz_dir = ctx.data_dir / "buzz"
    buzz_dir.mkdir(parents=True, exist_ok=True)

    if manual_text:
        prompt = build_pivot_prompt(manual_text)
        prompt_file = buzz_dir / "pivot_prompt_manual.md"
        prompt_file.write_text(prompt, encoding="utf-8")
        response_file = buzz_dir / "pivot_response_manual.json"
        print(f"✅ プロンプト保存: {prompt_file}")
        print(f"\n【Claude Codeセッション対応】")
        print(f"プロンプトを読んでJSON生成後、--apply で登録:")
        print(f"  python3 buzz_pivot.py --config configs/ronginooth_ai.yml --apply {response_file} --source '{manual_text[:40]}'")
        return

    # stats.csvからTOP投稿を検出
    top_posts = get_top_posts(ctx.stats_file, ctx.pivot_log, top_n)
    if not top_posts:
        print("バズピボットの対象となる投稿がありません。")
        return

    for rank, post in enumerate(top_posts, 1):
        source_text = post.get("text_preview", "")
        thread_id = post["thread_id"]
        print(f"\n{'='*50}")
        print(f"TOP{rank}（スコア: {post['score']:.0f}）")
        print(f"  元: {source_text}…")

        full_text = source_text
        if ctx.log_file.exists():
            log = json.loads(ctx.log_file.read_text())
            for entry in log:
                if entry.get("thread_id") == thread_id:
                    full_text = entry.get("text", source_text)
                    break

        prompt = build_pivot_prompt(full_text)
        short_id = thread_id[:8]
        prompt_file = buzz_dir / f"pivot_prompt_{short_id}.md"
        response_file = buzz_dir / f"pivot_response_{short_id}.json"
        prompt_file.write_text(prompt, encoding="utf-8")

        print(f"  ✅ プロンプト保存: {prompt_file}")
        print(f"  【Claude Codeセッション対応】")
        print(f"  プロンプトを読んでJSON生成後、--apply で登録:")
        print(f"  python3 buzz_pivot.py --config configs/ronginooth_ai.yml --apply {response_file} --source '{full_text[:40]}'")

    print(f"\n{'='*50}")
    print("プロンプト生成完了。Claude Codeで各プロンプトを処理してください。")


if __name__ == "__main__":
    ctx = get_context()
    run(ctx)
