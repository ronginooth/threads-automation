"""
アカウント分析スクリプト
config.yml のnote URLとXアカウントを分析し、
投稿生成に必要なプロフィール情報を data/account_profile.md に保存する

使い方:
  python3 prepare.py --config configs/ronginooth_ai.yml
  python3 prepare.py --config configs/ronginooth_ai.yml --force

【Claude Codeセッション対応モード】
API呼び出しは行わず、分析プロンプトをファイルに保存する。
Claude Code がプロンプトを読んでaccount_profile.mdを生成・保存する。
"""
import re
import subprocess
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.account_context import get_context


def find_note_content(note_url: str, search_paths: list[str]) -> str:
    """vault内からnote URLに一致する記事のローカルコピーを検索"""
    for search_path in search_paths:
        path = Path(search_path)
        if not path.exists():
            continue
        for md_file in path.rglob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
                if note_url in content:
                    print(f"  📄 記事を発見: {md_file}")
                    return content
            except (UnicodeDecodeError, PermissionError):
                continue
    return ""


def fetch_note_via_playwright(note_url: str) -> str:
    """Playwrightでnote記事の無料部分を取得（フォールバック）"""
    script = f"""
import asyncio
from playwright.async_api import async_playwright

async def fetch():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("{note_url}", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)
        content = await page.evaluate('''() => {{
            const article = document.querySelector('article') || document.querySelector('[class*="note-body"]') || document.body;
            return article ? article.innerText : document.body.innerText;
        }}''')
        await browser.close()
        return content

print(asyncio.run(fetch()))
"""
    try:
        result = subprocess.run(
            ["python3", "-c", script],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0 and result.stdout.strip():
            print("  🌐 Playwrightで記事を取得しました")
            return result.stdout.strip()
        print(f"  ⚠️ Playwright取得失敗: {result.stderr[:200]}")
    except Exception as e:
        print(f"  ⚠️ Playwright実行エラー: {e}")
    return ""


def find_x_posts(x_account: str, search_paths: list[str]) -> str:
    """vault内からXアカウントの投稿履歴を検索"""
    account_clean = x_account.lstrip("@")
    texts = []
    for search_path in search_paths:
        path = Path(search_path)
        if not path.exists():
            continue
        for md_file in path.rglob("*.md"):
            try:
                name_lower = md_file.name.lower()
                if account_clean.lower() in name_lower or "ronginooth" in name_lower:
                    content = md_file.read_text(encoding="utf-8")
                    if "トーン" in md_file.name or "Thread by" in md_file.name or account_clean in content:
                        texts.append(f"--- {md_file.name} ---\n{content[:3000]}")
            except (UnicodeDecodeError, PermissionError):
                continue
    return "\n\n".join(texts[:5])


def build_profile_prompt(config: dict, note_content: str, x_posts: str) -> str:
    """アカウントプロフィール生成プロンプトを組み立てて返す"""
    return f"""以下の情報を分析して、Threads自動投稿のためのアカウントプロフィールを生成してください。

## 入力情報

### Threadsアカウント: {config['account']}
### Xアカウント: {config.get('x_account', '不明')}
### 売りたいnote記事URL: {config['note_url']}

### note記事の内容（ローカルコピー）
{note_content[:8000] if note_content else '（取得できませんでした）'}

### Xアカウントの投稿・トーン情報
{x_posts[:4000] if x_posts else '（取得できませんでした）'}

## 出力フォーマット（以下のMarkdownをそのまま出力してください）

# アカウントプロフィール

## ペルソナ
（この人は何者か。経歴・専門性・立場を1-2文で）

## トーン・口調
（投稿の文体。一人称、語尾のパターン、よく使う表現を箇条書きで）

## 発信テーマ
（主に何について発信しているか。優先度順に箇条書き）

## ターゲット読者
（誰に向けて書いているか。具体的なペルソナを1-2文で）

## note記事の要約
（売りたい記事の核心。何を提供していて、読者の何を解決するか）

## L2（教育）テーマリスト
（note記事の内容から逆算した、無料で小出しにできる教育テーマ。7-10個）
1. ...
2. ...

## L3（導線）パターン
（体験談・気づきの結末でnoteに触れる自然なパターン。3-5個の例文）
- 例1: ...
- 例2: ...

## 避けるべきこと
（ペルソナと矛盾する表現、やってはいけないこと）
"""


def run(ctx=None):
    force = "--force" in sys.argv

    if ctx is None:
        ctx = get_context()

    config = ctx.config
    profile_file = ctx.profile_file

    if profile_file.exists() and not force:
        print(f"✅ プロフィールは既に存在します: {profile_file}")
        print("   再分析するには --force オプションを追加してください")
        return

    print(f"アカウント分析開始: {config['account']}")

    print("\n① note記事を検索中...")
    note_content = find_note_content(
        config["note_url"],
        config.get("vault_search_paths", [])
    )
    if not note_content:
        print("  ローカルに見つからないため、Playwrightで取得を試みます...")
        note_content = fetch_note_via_playwright(config["note_url"])
    if not note_content:
        print("  ⚠️ 記事内容を取得できませんでした。手動で data/note_article.md に保存してください。")

    print("\n② Xアカウントの情報を検索中...")
    x_posts = find_x_posts(
        config.get("x_account", ""),
        config.get("vault_search_paths", [])
    )
    if x_posts:
        print(f"  📄 X関連ファイルを発見")
    else:
        print("  ⚠️ X投稿の情報が見つかりませんでした")

    print("\n③ プロフィール生成プロンプトを保存中...")
    prompt = build_profile_prompt(config, note_content, x_posts)
    prompt_file = ctx.data_dir / "prepare_prompt.md"
    prompt_file.write_text(prompt, encoding="utf-8")

    print(f"\n✅ プロンプト保存: {prompt_file}")
    print(f"\n【Claude Codeセッション対応】")
    print(f"プロンプトを読んでアカウントプロフィールを生成し、以下に保存してください:")
    print(f"  prompt: {prompt_file}")
    print(f"  output: {profile_file}")


if __name__ == "__main__":
    ctx = get_context()
    run(ctx)
