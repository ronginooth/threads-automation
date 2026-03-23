"""
承認スクリプト
posts/YYYY-MM-DD_week/all_posts.md を読んでキューに登録する
使い方: python3 approve.py posts/2026-03-30_week
"""
import sys
import re
from datetime import datetime, timedelta
from pathlib import Path

QUEUE_DIR = Path(__file__).parent / "data" / "queue"

TIMES = ["07:00", "10:00", "13:00", "17:00", "21:00"]


def parse_posts(content: str) -> list[dict]:
    """all_posts.md から投稿文を抽出（型・レイヤー情報も取得）"""
    pattern = r"### Day(\d+)-投稿(\d+)（[^）]*）型:\s*([^\||\n]*?)(?:\s*\|\s*(L[123]))?\s*\n---\n(.*?)\n---"
    matches = re.findall(pattern, content, re.DOTALL)
    posts = []
    for day, num, post_type, layer, text in matches:
        posts.append({
            "day": int(day),
            "num": int(num),
            "type": post_type.strip(),
            "layer": layer.strip() if layer else "L1",
            "text": text.strip(),
        })
    return posts


def run():
    if len(sys.argv) < 2:
        print("使い方: python3 approve.py posts/2026-03-30_week")
        return

    week_dir = Path(sys.argv[1])
    all_posts_file = week_dir / "all_posts.md"

    if not all_posts_file.exists():
        print(f"ファイルが見つかりません: {all_posts_file}")
        return

    content = all_posts_file.read_text(encoding="utf-8")
    posts = parse_posts(content)

    if not posts:
        print("投稿文が解析できませんでした。フォーマットを確認してください。")
        return

    # week_dir名から週の開始日を取得
    week_start_str = week_dir.name.replace("_week", "")
    week_start = datetime.strptime(week_start_str, "%Y-%m-%d")

    created = 0
    for post in posts:
        date = week_start + timedelta(days=post["day"] - 1)
        time_str = TIMES[(post["num"] - 1) % len(TIMES)]
        type_slug = post["type"].replace(" ", "_") or f"post{post['num']}"
        filename = f"{date.strftime('%Y-%m-%d')}_{post['num']}_{type_slug}.md"
        filepath = QUEUE_DIR / filename

        filepath.write_text(
            f"---\nday: {post['day']}\ntype: {post['type']}\nlayer: {post['layer']}\nscheduled: {date.strftime('%Y-%m-%d')} {time_str}\n---\n\n{post['text']}\n",
            encoding="utf-8",
        )
        print(f"✅ {filename}")
        created += 1

    print(f"\n{created}本をキューに登録しました。")
    print("スケジューラーが自動で投稿します。")


if __name__ == "__main__":
    run()
