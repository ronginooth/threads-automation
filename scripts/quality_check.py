"""
品質チェックスクリプト
生成された投稿を自動採点し、品質が低いものを棄却する

機能:
1. Claude APIで10項目×10点の品質スコア採点（7.0未満は棄却）
2. 過去投稿との類似度チェック（0.85以上は棄却）
3. 投稿パターンの偏りチェック（同じtypeが4連続なら警告）
"""
import os
import re
import json
import math
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collections import Counter
from datetime import datetime
from dotenv import load_dotenv
import anthropic
from lib.account_context import get_context

load_dotenv()

SCORE_THRESHOLD = 7.0
SIMILARITY_THRESHOLD = 0.85
MAX_CONSECUTIVE_SAME_TYPE = 3


# ========================================
# 1. 品質スコア採点
# ========================================

def score_post(text: str, post_type: str = "") -> dict:
    """Claude APIで投稿を10項目採点し、結果を返す"""
    client = anthropic.Anthropic()

    prompt = f"""以下のThreads投稿を10項目で採点してください。
各項目10点満点で、整数で採点してください。

【投稿文】
{text}

【投稿タイプ】
{post_type or "不明"}

【採点基準】
1. hook: フックの強さ（1行目で読者が止まるか）
2. useful: 有益性（読んで得があるか）
3. specific: 具体性（抽象論で終わっていないか）
4. rhythm: テンポ感（読みやすいリズムか）
5. persona: ペルソナ一致度（研究歴20年のPhDの声に聞こえるか）
6. original: 独自性（他でも言えることじゃないか）
7. emotion: 感情トリガー（共感・驚き・怒りを生むか）
8. action: 行動喚起（リプ・保存したくなるか）
9. length: 文字数の適切さ（Threadsに適した長さか）
10. natural: 自然さ（AI臭い定型表現がないか）

JSON形式で返してください。コメントや説明は不要です。
{{"hook":X,"useful":X,"specific":X,"rhythm":X,"persona":X,"original":X,"emotion":X,"action":X,"length":X,"natural":X}}"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text.strip()
    start = response_text.find("{")
    end = response_text.rfind("}") + 1
    if start != -1 and end > start:
        scores = json.loads(response_text[start:end])
        scores["average"] = sum(scores.values()) / len(scores)
        return scores
    raise ValueError(f"スコアの解析に失敗: {response_text}")


# ========================================
# 2. 類似度チェック（TF-IDF不要の軽量版）
# ========================================

def tokenize(text: str) -> list[str]:
    """日本語テキストを文字bi-gramに分割（形態素解析不要）"""
    text = re.sub(r'\s+', '', text)
    return [text[i:i+2] for i in range(len(text) - 1)]


def cosine_similarity(text_a: str, text_b: str) -> float:
    """2つのテキストのコサイン類似度（文字bi-gram）"""
    tokens_a = Counter(tokenize(text_a))
    tokens_b = Counter(tokenize(text_b))

    if not tokens_a or not tokens_b:
        return 0.0

    common = set(tokens_a.keys()) & set(tokens_b.keys())
    dot = sum(tokens_a[t] * tokens_b[t] for t in common)
    norm_a = math.sqrt(sum(v * v for v in tokens_a.values()))
    norm_b = math.sqrt(sum(v * v for v in tokens_b.values()))

    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def load_past_texts(log_file, posted_dir, limit: int = 100) -> list[str]:
    """過去の投稿テキストを取得（posted/ + posted_log.json）"""
    texts = []

    # posted_log.jsonから
    if log_file.exists():
        log = json.loads(log_file.read_text())
        for entry in log[-limit:]:
            if entry.get("text"):
                texts.append(entry["text"])

    # posted/フォルダから
    posted_files = sorted(posted_dir.glob("*.md"))[-limit:]
    for f in posted_files:
        content = f.read_text(encoding="utf-8")
        content = re.sub(r"^---.*?---\s*", "", content, flags=re.DOTALL)
        text = content.strip()
        if text and text not in texts:
            texts.append(text)

    return texts[-limit:]


def check_similarity(new_text: str, past_texts: list[str]) -> tuple[float, str]:
    """新規投稿と過去投稿の最大類似度と最も似た投稿を返す"""
    max_sim = 0.0
    most_similar = ""
    for past in past_texts:
        sim = cosine_similarity(new_text, past)
        if sim > max_sim:
            max_sim = sim
            most_similar = past[:60]
    return max_sim, most_similar


# ========================================
# 3. パターンローテーションチェック
# ========================================

def get_recent_types(posted_dir, queue_dir, n: int = 10) -> list[str]:
    """キューと投稿済みファイルから直近n件のtypeを取得"""
    types = []

    # posted/から
    for f in sorted(posted_dir.glob("*.md")):
        content = f.read_text(encoding="utf-8")
        match = re.search(r'^type:\s*(.+)$', content, re.MULTILINE)
        if match:
            types.append(match.group(1).strip())

    # queue/から（scheduled順）
    queue_files = sorted(queue_dir.glob("*.md"))
    for f in queue_files:
        content = f.read_text(encoding="utf-8")
        match = re.search(r'^type:\s*(.+)$', content, re.MULTILINE)
        if match:
            types.append(match.group(1).strip())

    return types[-n:]


def check_pattern_rotation(new_type: str, posted_dir, queue_dir) -> dict:
    """パターンの偏りをチェック"""
    recent = get_recent_types(posted_dir, queue_dir, 10)
    result = {"ok": True, "warning": "", "recent_types": recent}

    if not recent:
        return result

    # 直近3件と同じtypeかチェック
    last_3 = recent[-MAX_CONSECUTIVE_SAME_TYPE:]
    if len(last_3) == MAX_CONSECUTIVE_SAME_TYPE and all(t == new_type for t in last_3):
        result["ok"] = False
        result["warning"] = f"「{new_type}」が{MAX_CONSECUTIVE_SAME_TYPE}件連続しています。別のtypeに変更してください。"

    return result


# ========================================
# メイン処理
# ========================================

def parse_frontmatter(path: Path) -> dict:
    """frontmatterを辞書で返す"""
    content = path.read_text(encoding="utf-8")
    match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return {}
    fm = {}
    for line in match.group(1).split("\n"):
        if ":" in line:
            key, val = line.split(":", 1)
            fm[key.strip()] = val.strip()
    return fm


def parse_body(path: Path) -> str:
    """frontmatterを除いた本文を返す"""
    content = path.read_text(encoding="utf-8")
    return re.sub(r"^---.*?---\s*", "", content, flags=re.DOTALL).strip()


def check_file(path: Path, ctx, past_texts: list[str] | None = None) -> dict:
    """1ファイルの品質チェックを実行"""
    fm = parse_frontmatter(path)
    body = parse_body(path)
    post_type = fm.get("type", "")

    result = {
        "file": path.name,
        "type": post_type,
        "passed": True,
        "reasons": [],
    }

    if not body:
        result["passed"] = False
        result["reasons"].append("本文が空です")
        return result

    # 1. 品質スコア
    try:
        scores = score_post(body, post_type)
        result["scores"] = scores
        avg = scores["average"]
        if avg < SCORE_THRESHOLD:
            result["passed"] = False
            result["reasons"].append(f"品質スコア {avg:.1f} < {SCORE_THRESHOLD}（基準未達）")
        print(f"  スコア: {avg:.1f}/10 {scores}")
    except Exception as e:
        print(f"  スコア採点エラー: {e}")
        result["score_error"] = str(e)

    # 2. 類似度チェック
    if past_texts is None:
        past_texts = load_past_texts(ctx.log_file, ctx.posted_dir)

    if past_texts:
        max_sim, most_similar = check_similarity(body, past_texts)
        result["max_similarity"] = round(max_sim, 3)
        result["most_similar_to"] = most_similar
        if max_sim >= SIMILARITY_THRESHOLD:
            result["passed"] = False
            result["reasons"].append(
                f"類似度 {max_sim:.2f} >= {SIMILARITY_THRESHOLD}（「{most_similar}…」と類似）"
            )
        print(f"  類似度: {max_sim:.2f}（最も似た投稿: {most_similar}…）")

    # 3. パターンローテーション
    if post_type:
        rotation = check_pattern_rotation(post_type, ctx.posted_dir, ctx.queue_dir)
        result["rotation"] = rotation
        if not rotation["ok"]:
            result["reasons"].append(rotation["warning"])
            print(f"  パターン警告: {rotation['warning']}")

    return result


def check_queue(ctx=None):
    """キュー内の全投稿を品質チェック"""
    if ctx is None:
        ctx = get_context()

    files = sorted(ctx.queue_dir.glob("*.md"))
    if not files:
        print("キューに投稿がありません。")
        return

    past_texts = load_past_texts(ctx.log_file, ctx.posted_dir)

    # reject_log
    reject_log = []
    if ctx.reject_log.exists():
        reject_log = json.loads(ctx.reject_log.read_text())

    print(f"品質チェック開始: {len(files)}件")
    print(f"過去投稿: {len(past_texts)}件をロード済み")
    print("=" * 50)

    passed = 0
    failed = 0

    for f in files:
        print(f"\n📝 {f.name}")
        result = check_file(f, ctx, past_texts)

        if result["passed"]:
            print(f"  ✅ 合格")
            passed += 1
        else:
            print(f"  ❌ 不合格: {', '.join(result['reasons'])}")
            failed += 1
            reject_log.append({
                "file": f.name,
                "checked_at": datetime.now().isoformat(),
                "reasons": result["reasons"],
                "scores": result.get("scores"),
                "similarity": result.get("max_similarity"),
            })

    ctx.reject_log.write_text(json.dumps(reject_log, ensure_ascii=False, indent=2))

    print("\n" + "=" * 50)
    print(f"結果: ✅ {passed}件合格 / ❌ {failed}件不合格")
    if failed > 0:
        print(f"詳細は {ctx.reject_log} を確認してください。")


if __name__ == "__main__":
    ctx = get_context()
    check_queue(ctx)
