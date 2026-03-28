"""
品質チェックスクリプト
生成された投稿を自動採点し、品質が低いものを棄却する

機能:
1. Claude Code で10項目×10点の品質スコア採点（7.0未満は棄却）
2. 過去投稿との類似度チェック（0.85以上は棄却）純Pythonで実行
3. 投稿パターンの偏りチェック（同じtypeが4連続なら警告）純Pythonで実行
4. 事実確認チェック（Claude Codeで実行）

使い方:
  python3 quality_check.py --config configs/ronginooth_ai.yml
    → キュー内の投稿を採点リクエストとしてファイルに保存

  python3 quality_check.py --config configs/ronginooth_ai.yml --apply data/.../quality_response.json
    → Claude Codeが生成したJSONを読んで棄却処理を実行

【Claude Codeセッション対応モード】
API呼び出しは行わず、採点リクエストをファイルに保存する。
Claude Code がリクエストを読んでJSONで採点結果を返し、--apply で棄却処理を実行する。
"""
import re
import json
import math
import argparse
from pathlib import Path
from collections import Counter
from datetime import datetime

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.account_context import get_context

SCORE_THRESHOLD = 7.0
SIMILARITY_THRESHOLD = 0.85
MAX_CONSECUTIVE_SAME_TYPE = 3


# ========================================
# 類似度チェック（純Python・APIなし）
# ========================================

def tokenize(text: str) -> list[str]:
    text = re.sub(r'\s+', '', text)
    return [text[i:i+2] for i in range(len(text) - 1)]


def cosine_similarity(text_a: str, text_b: str) -> float:
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
    texts = []
    if log_file.exists():
        log = json.loads(log_file.read_text())
        for entry in log[-limit:]:
            if entry.get("text"):
                texts.append(entry["text"])
    posted_files = sorted(posted_dir.glob("*.md"))[-limit:]
    for f in posted_files:
        content = f.read_text(encoding="utf-8")
        content = re.sub(r"^---.*?---\s*", "", content, flags=re.DOTALL)
        text = content.strip()
        if text and text not in texts:
            texts.append(text)
    return texts[-limit:]


def check_similarity(new_text: str, past_texts: list[str]) -> tuple[float, str]:
    max_sim = 0.0
    most_similar = ""
    for past in past_texts:
        sim = cosine_similarity(new_text, past)
        if sim > max_sim:
            max_sim = sim
            most_similar = past[:60]
    return max_sim, most_similar


# ========================================
# パターンローテーションチェック（純Python・APIなし）
# ========================================

def get_recent_types(posted_dir, queue_dir, n: int = 10) -> list[str]:
    types = []
    for f in sorted(posted_dir.glob("*.md")):
        content = f.read_text(encoding="utf-8")
        match = re.search(r'^type:\s*(.+)$', content, re.MULTILINE)
        if match:
            types.append(match.group(1).strip())
    queue_files = sorted(queue_dir.glob("*.md"))
    for f in queue_files:
        content = f.read_text(encoding="utf-8")
        match = re.search(r'^type:\s*(.+)$', content, re.MULTILINE)
        if match:
            types.append(match.group(1).strip())
    return types[-n:]


def check_pattern_rotation(new_type: str, posted_dir, queue_dir) -> dict:
    recent = get_recent_types(posted_dir, queue_dir, 10)
    result = {"ok": True, "warning": "", "recent_types": recent}
    if not recent:
        return result
    last_3 = recent[-MAX_CONSECUTIVE_SAME_TYPE:]
    if len(last_3) == MAX_CONSECUTIVE_SAME_TYPE and all(t == new_type for t in last_3):
        result["ok"] = False
        result["warning"] = f"「{new_type}」が{MAX_CONSECUTIVE_SAME_TYPE}件連続しています。"
    return result


# ========================================
# ファイルパース
# ========================================

def parse_frontmatter(path: Path) -> dict:
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
    content = path.read_text(encoding="utf-8")
    return re.sub(r"^---.*?---\s*", "", content, flags=re.DOTALL).strip()


# ========================================
# バッチ採点リクエスト生成
# ========================================

def build_check_request(files: list[Path], ctx) -> str:
    """キュー内全投稿の採点リクエストを組み立てて返す"""
    posts_text = ""
    for i, f in enumerate(files, 1):
        fm = parse_frontmatter(f)
        body = parse_body(f)
        posts_text += f"""
### 投稿{i}: {f.name}
タイプ: {fm.get('type', '不明')}
本文:
{body}
"""

    response_file = ctx.data_dir / "quality_response.json"

    return f"""# 品質チェックリクエスト
生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M')}
対象: {len(files)}件
出力先: {response_file}

## 採点基準（各項目10点満点）
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

## 事実確認基準
- 専門分野のルール・慣習として述べている内容は正確か
- 断定的な主張が特定文脈でしか成り立たないのに一般化されていないか
- 主観・感想・体験談には事実チェック不要（verdict: "pass"）

## 採点対象投稿
{posts_text}

## 出力フォーマット
以下のJSON配列を {response_file} に保存してください。
[
  {{
    "file": "ファイル名",
    "scores": {{"hook":X,"useful":X,"specific":X,"rhythm":X,"persona":X,"original":X,"emotion":X,"action":X,"length":X,"natural":X}},
    "average": X.X,
    "fact_check": {{"verdict": "pass/warn/fail", "issues": []}},
    "comment": "改善が必要な点（任意）"
  }},
  ...
]
"""


# ========================================
# --apply モード: JSONを読んで棄却処理
# ========================================

def apply_check_results(response_file: Path, ctx):
    """Claude Codeが生成した採点JSONを読んで棄却処理を実行"""
    results = json.loads(response_file.read_text(encoding="utf-8"))

    # 類似度チェック（純Python）
    past_texts = load_past_texts(ctx.log_file, ctx.posted_dir)

    reject_log = []
    if ctx.reject_log.exists():
        reject_log = json.loads(ctx.reject_log.read_text())

    passed = 0
    failed = 0

    print(f"品質チェック結果を処理中: {len(results)}件")
    print("=" * 50)

    for result in results:
        filename = result["file"]
        filepath = ctx.queue_dir / filename
        if not filepath.exists():
            print(f"  ⚠️ ファイルが見つかりません: {filename}")
            continue

        body = parse_body(filepath)
        fm = parse_frontmatter(filepath)
        post_type = fm.get("type", "")

        reasons = []
        avg = result.get("average", 10.0)

        print(f"\n📝 {filename}  スコア: {avg:.1f}/10")

        # 1. スコアチェック
        if avg < SCORE_THRESHOLD:
            reasons.append(f"品質スコア {avg:.1f} < {SCORE_THRESHOLD}")

        # 2. 事実確認
        fc = result.get("fact_check", {})
        if fc.get("verdict") == "fail":
            issues = "; ".join(i.get("claim", "") + " → " + i.get("problem", "") for i in fc.get("issues", []))
            reasons.append(f"事実確認NG: {issues}")
            print(f"  ❌ 事実確認NG: {issues}")
        elif fc.get("verdict") == "warn":
            issues = "; ".join(i.get("claim", "") + " → " + i.get("problem", "") for i in fc.get("issues", []))
            print(f"  ⚠️ 事実確認注意: {issues}")

        # 3. 類似度チェック
        if past_texts and body:
            max_sim, most_similar = check_similarity(body, past_texts)
            if max_sim >= SIMILARITY_THRESHOLD:
                reasons.append(f"類似度 {max_sim:.2f} >= {SIMILARITY_THRESHOLD}（「{most_similar}…」と類似）")
            print(f"  類似度: {max_sim:.2f}")

        # 4. パターンローテーション
        if post_type:
            rotation = check_pattern_rotation(post_type, ctx.posted_dir, ctx.queue_dir)
            if not rotation["ok"]:
                reasons.append(rotation["warning"])
                print(f"  パターン警告: {rotation['warning']}")

        if reasons:
            print(f"  ❌ 不合格: {', '.join(reasons)}")
            failed += 1
            reject_log.append({
                "file": filename,
                "checked_at": datetime.now().isoformat(),
                "reasons": reasons,
                "scores": result.get("scores"),
                "average": avg,
            })
        else:
            print(f"  ✅ 合格")
            passed += 1

    ctx.reject_log.write_text(json.dumps(reject_log, ensure_ascii=False, indent=2))

    print("\n" + "=" * 50)
    print(f"結果: ✅ {passed}件合格 / ❌ {failed}件不合格")
    if failed > 0:
        print(f"詳細は {ctx.reject_log} を確認してください。")


# ========================================
# メイン
# ========================================

def check_queue(ctx=None):
    """キュー内の全投稿の採点リクエストを生成"""
    if ctx is None:
        ctx = get_context()

    files = sorted(ctx.queue_dir.glob("*.md"))
    if not files:
        print("キューに投稿がありません。")
        return

    request = build_check_request(files, ctx)
    request_file = ctx.data_dir / "quality_request.md"
    request_file.write_text(request, encoding="utf-8")

    response_file = ctx.data_dir / "quality_response.json"

    print(f"✅ 採点リクエスト保存: {request_file}（{len(files)}件）")
    print(f"\n【Claude Codeセッション対応】")
    print(f"リクエストを読んで採点結果JSONを生成し、以下に保存してください:")
    print(f"  request: {request_file}")
    print(f"  output:  {response_file}")
    print(f"保存後、以下で棄却処理を実行:")
    print(f"  python3 quality_check.py --config configs/ronginooth_ai.yml --apply {response_file}")


def run(ctx=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", help="設定ファイルのパス")
    parser.add_argument("--apply", help="Claude Codeが生成した採点JSONのパス")
    args, _ = parser.parse_known_args()

    if ctx is None:
        ctx = get_context()

    if args.apply:
        apply_check_results(Path(args.apply), ctx)
    else:
        check_queue(ctx)


if __name__ == "__main__":
    ctx = get_context()
    run(ctx)
