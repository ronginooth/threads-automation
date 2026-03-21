"""
スケジューラー
毎日 08:00, 12:00, 17:00 に投稿
毎日 23:00 に統計収集
毎週日曜 22:00 に統計→トレンド収集→バズ分析→投稿文生成

起動方法: python3 scheduler.py
（バックグラウンドで常時起動しておく）
"""
import schedule
import time
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).parent
PYTHON = sys.executable


def run_post():
    print("▶ 投稿実行")
    subprocess.run([PYTHON, str(BASE / "post.py")])


def run_stats():
    print("▶ 統計収集")
    subprocess.run([PYTHON, str(BASE / "stats.py")])


# 投稿スケジュール（1日3回）
schedule.every().day.at("08:00").do(run_post)
schedule.every().day.at("12:00").do(run_post)
schedule.every().day.at("17:00").do(run_post)

# 統計収集（毎日深夜）
schedule.every().day.at("23:00").do(run_stats)

print("✅ スケジューラー起動中")
print("  投稿: 08:00 / 12:00 / 17:00")
print("  統計: 23:00")
print("  週次分析・生成は手動: python3 weekly.py")
print("  終了するには Ctrl+C")

while True:
    schedule.run_pending()
    time.sleep(30)
