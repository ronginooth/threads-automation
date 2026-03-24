"""
スケジューラー（マルチアカウント対応）
configs/内の全アカウントに対して投稿・統計を実行

起動方法: python3 scheduler.py
（バックグラウンドで常時起動しておく）
"""
import schedule
import time
import subprocess
import sys
from pathlib import Path
import yaml

BASE = Path(__file__).parent
PYTHON = sys.executable
CONFIGS_DIR = BASE / "configs"


def get_all_configs() -> list[Path]:
    if CONFIGS_DIR.exists():
        return sorted(CONFIGS_DIR.glob("*.yml"))
    return []


def run_for_all(script: str):
    configs = get_all_configs()
    for cfg in configs:
        print(f"▶ {script} ({cfg.stem})")
        subprocess.run([PYTHON, str(BASE / script), "--config", str(cfg)])


def run_post():
    run_for_all("post.py")


def run_stats():
    run_for_all("stats.py")


# 投稿スケジュール（1日5回 — 各アカウントのtimesはpost.py内で制御）
schedule.every().day.at("07:00").do(run_post)
schedule.every().day.at("10:00").do(run_post)
schedule.every().day.at("13:00").do(run_post)
schedule.every().day.at("17:00").do(run_post)
schedule.every().day.at("21:00").do(run_post)

# 統計収集（毎日深夜）
schedule.every().day.at("23:00").do(run_stats)

configs = get_all_configs()
print("✅ スケジューラー起動中")
print(f"  アカウント: {[c.stem for c in configs]}")
print("  投稿: 07:00 / 10:00 / 13:00 / 17:00 / 21:00")
print("  統計: 23:00")
print("  週次: python3 run_all.py weekly")
print("  終了するには Ctrl+C")

while True:
    schedule.run_pending()
    time.sleep(30)
