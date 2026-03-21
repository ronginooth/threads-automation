"""Threads API の共通処理"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("THREADS_ACCESS_TOKEN")
USER_ID = os.getenv("THREADS_USER_ID")
BASE_URL = "https://graph.threads.net/v1.0"


def create_post(text: str) -> str:
    """投稿コンテナを作成してpost_idを返す"""
    res = requests.post(
        f"{BASE_URL}/{USER_ID}/threads",
        params={
            "media_type": "TEXT",
            "text": text,
            "access_token": TOKEN,
        },
    )
    res.raise_for_status()
    return res.json()["id"]


def publish_post(creation_id: str) -> str:
    """コンテナを公開してthread_idを返す"""
    res = requests.post(
        f"{BASE_URL}/{USER_ID}/threads_publish",
        params={
            "creation_id": creation_id,
            "access_token": TOKEN,
        },
    )
    res.raise_for_status()
    return res.json()["id"]


def get_insights(thread_id: str) -> dict:
    """投稿のインサイト（いいね・インプ等）を取得"""
    res = requests.get(
        f"{BASE_URL}/{thread_id}/insights",
        params={
            "metric": "views,likes,replies,reposts,quotes",
            "access_token": TOKEN,
        },
    )
    res.raise_for_status()
    data = res.json().get("data", [])
    return {item["name"]: item["values"][0]["value"] for item in data}


def get_my_posts(limit: int = 25) -> list:
    """自分の最近の投稿一覧を取得"""
    res = requests.get(
        f"{BASE_URL}/{USER_ID}/threads",
        params={
            "fields": "id,text,timestamp,permalink",
            "limit": limit,
            "access_token": TOKEN,
        },
    )
    res.raise_for_status()
    return res.json().get("data", [])
