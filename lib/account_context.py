"""
アカウントコンテキスト
config YAMLを読み込み、パス・トークン・設定を一元管理する

使い方:
  from lib.account_context import get_context
  ctx = get_context()  # --config 引数を自動パース
  # ctx.queue_dir, ctx.token, ctx.config["account"] 等でアクセス
"""
import os
import argparse
from pathlib import Path
import yaml
from dotenv import load_dotenv

load_dotenv()

BASE = Path(__file__).parent.parent


class AccountContext:
    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.config = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
        self.name = self.config_path.stem  # e.g. "ronginooth_ai"

        # データディレクトリ（アカウントごとに分離）
        self.data_dir = BASE / "data" / self.name
        self.queue_dir = self.data_dir / "queue"
        self.posted_dir = self.data_dir / "posted"
        self.log_file = self.data_dir / "posted_log.json"
        self.stats_file = self.data_dir / "stats.csv"
        self.profile_file = self.data_dir / "account_profile.md"
        self.seen_file = self.data_dir / "seen_comments.json"
        self.reject_log = self.data_dir / "rejected_log.json"
        self.pivot_log = self.data_dir / "pivot_log.json"
        self.kill_switch = self.data_dir / "KILL_SWITCH"
        self.posts_dir = BASE / "posts" / self.name

        # バズ分析（全アカウント共有）
        self.buzz_dir = BASE / "data" / "buzz"
        niche = self.config.get("niche", "general")
        self.buzz_patterns_file = self.buzz_dir / "patterns" / f"{niche}.md"

        # API トークン（アカウント固有 → 汎用のフォールバック）
        suffix = self.name.upper()
        self.token = (
            os.getenv(f"THREADS_ACCESS_TOKEN_{suffix}")
            or os.getenv("THREADS_ACCESS_TOKEN")
        )
        self.user_id = (
            os.getenv(f"THREADS_USER_ID_{suffix}")
            or os.getenv("THREADS_USER_ID")
        )

        # config値のショートカット
        self.account = self.config.get("account", "")
        self.note_url = self.config.get("note_url", "")
        self.max_chars = self.config.get("max_chars", 200)
        self.times = self.config.get("times", ["07:00", "10:00", "13:00", "17:00", "21:00"])
        self.layers = self.config.get("layers", {"L1_共感": 21, "L2_教育": 10, "L3_導線": 4})
        self.niche = self.config.get("niche", "general")

    def ensure_dirs(self):
        """必要なディレクトリを作成"""
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self.posted_dir.mkdir(parents=True, exist_ok=True)
        self.posts_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)


def get_context() -> AccountContext:
    """--config 引数をパースしてAccountContextを返す"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="設定ファイルのパス (例: configs/ronginooth_ai.yml)")
    args, _ = parser.parse_known_args()
    ctx = AccountContext(args.config)
    ctx.ensure_dirs()
    return ctx
