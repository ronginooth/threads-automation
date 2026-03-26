"""Threads API の共通処理（マルチアカウント対応）"""
import requests

BASE_URL = "https://graph.threads.net/v1.0"


def create_post(text: str, token: str, user_id: str) -> str:
    """投稿コンテナを作成してpost_idを返す"""
    res = requests.post(
        f"{BASE_URL}/{user_id}/threads",
        params={
            "media_type": "TEXT",
            "text": text,
            "access_token": token,
        },
    )
    res.raise_for_status()
    return res.json()["id"]


def publish_post(creation_id: str, token: str, user_id: str) -> str:
    """コンテナを公開してthread_idを返す"""
    res = requests.post(
        f"{BASE_URL}/{user_id}/threads_publish",
        params={
            "creation_id": creation_id,
            "access_token": token,
        },
    )
    res.raise_for_status()
    return res.json()["id"]


def get_insights(thread_id: str, token: str) -> dict:
    """投稿のインサイト（いいね・インプ等）を取得"""
    res = requests.get(
        f"{BASE_URL}/{thread_id}/insights",
        params={
            "metric": "views,likes,replies,reposts,quotes",
            "access_token": token,
        },
    )
    res.raise_for_status()
    data = res.json().get("data", [])
    return {item["name"]: item["values"][0]["value"] for item in data}


def get_my_posts(token: str, user_id: str, limit: int = 25) -> list:
    """自分の最近の投稿一覧を取得"""
    res = requests.get(
        f"{BASE_URL}/{user_id}/threads",
        params={
            "fields": "id,text,timestamp,permalink",
            "limit": limit,
            "access_token": token,
        },
    )
    res.raise_for_status()
    return res.json().get("data", [])


def create_reply(text: str, reply_to_id: str, token: str, user_id: str) -> str:
    """リプライコンテナを作成してpost_idを返す"""
    res = requests.post(
        f"{BASE_URL}/{user_id}/threads",
        params={
            "media_type": "TEXT",
            "text": text,
            "reply_to_id": reply_to_id,
            "access_token": token,
        },
    )
    res.raise_for_status()
    return res.json()["id"]


def get_user_insights(token: str, user_id: str) -> dict:
    """ユーザーレベルのインサイト（プロフィールviews、リンクclicks等）を取得"""
    res = requests.get(
        f"{BASE_URL}/{user_id}/threads_insights",
        params={
            "metric": "views,likes,replies,reposts,quotes,followers_count,clicks",
            "access_token": token,
        },
    )
    res.raise_for_status()
    data = res.json().get("data", [])
    result = {}
    for item in data:
        name = item["name"]
        # total_value がある場合（followers_count等）
        if "total_value" in item:
            result[name] = item["total_value"].get("value", 0)
        # values 配列がある場合
        elif "values" in item and item["values"]:
            result[name] = item["values"][0].get("value", 0)
    return result


def get_user_posts(target_user_id: str, token: str, limit: int = 25) -> list:
    """公開ユーザーの投稿一覧を取得（バズ分析用）"""
    res = requests.get(
        f"{BASE_URL}/{target_user_id}/threads",
        params={
            "fields": "id,text,timestamp,permalink",
            "limit": limit,
            "access_token": token,
        },
    )
    res.raise_for_status()
    return res.json().get("data", [])
