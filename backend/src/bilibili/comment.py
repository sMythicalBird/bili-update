"""B站评论 API 客户端。"""

import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

API_REPLY_MAIN = "https://api.bilibili.com/x/v2/reply/main"
API_REPLY_REPLY = "https://api.bilibili.com/x/v2/reply/reply"
TIMEOUT = 15
REQUEST_INTERVAL = 0.5
PAGE_SIZE = 20
MAX_PAGES = 50  # 安全上限，防止异常死循环


def fetch_comments(
    cookie: str,
    user_agent: str,
    oid: str,
    comment_type: int,
    max_pages: int = MAX_PAGES,
) -> list[dict[str, Any]]:
    """拉取一级评论列表（含置顶评论），翻页到底。

    Args:
        cookie: B站 Cookie
        user_agent: User-Agent
        oid: 评论对象ID（动态的 rid_str）
        comment_type: 评论类型（动态为 11）
        max_pages: 最大翻页数（安全上限）

    Returns:
        评论列表（置顶评论在最前）
    """
    headers = _make_headers(cookie, user_agent)
    all_comments: list[dict[str, Any]] = []
    next_page = 0

    for page in range(max_pages):
        time.sleep(REQUEST_INTERVAL)

        try:
            resp = requests.get(
                API_REPLY_MAIN,
                params={"oid": oid, "type": comment_type, "mode": 2, "next": next_page},
                headers=headers,
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.warning("拉取评论失败 (oid=%s, page=%d): %s", oid, page, e)
            break

        data = resp.json()
        if data.get("code") != 0:
            logger.warning(
                "评论接口返回错误 code=%s (oid=%s): %s",
                data.get("code"), oid, data.get("message") or data.get("msg") or "",
            )
            break

        page_data = data.get("data", {})
        replies = page_data.get("replies", [])
        top_replies = page_data.get("top_replies", [])

        # 第一页拉取置顶评论
        if page == 0:
            for r in top_replies:
                all_comments.append(_parse_comment(r, oid))

        for r in replies:
            all_comments.append(_parse_comment(r, oid))

        if not replies:
            break

        cursor = page_data.get("cursor", {})
        if cursor.get("is_end", True):
            break
        next_page = cursor.get("next", 0)
        if next_page == 0:
            break

    return all_comments


def fetch_sub_replies(
    cookie: str,
    user_agent: str,
    oid: str,
    comment_type: int,
    root_rpid: str,
    max_pages: int = MAX_PAGES,
) -> list[dict[str, Any]]:
    """拉取子回复（楼中楼），翻页到底。

    Args:
        cookie: B站 Cookie
        user_agent: User-Agent
        oid: 评论对象ID
        comment_type: 评论类型
        root_rpid: 根评论 rpid
        max_pages: 最大翻页数（安全上限）

    Returns:
        子回复列表
    """
    headers = _make_headers(cookie, user_agent)
    all_replies: list[dict[str, Any]] = []

    for page in range(1, max_pages + 1):
        time.sleep(REQUEST_INTERVAL)

        try:
            resp = requests.get(
                API_REPLY_REPLY,
                params={
                    "oid": oid,
                    "type": comment_type,
                    "root": root_rpid,
                    "ps": PAGE_SIZE,
                    "pn": page,
                },
                headers=headers,
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.warning("拉取子回复失败 (root=%s, page=%d): %s", root_rpid, page, e)
            break

        data = resp.json()
        if data.get("code") != 0:
            logger.warning(
                "子回复接口返回错误 code=%s (oid=%s, root=%s): %s",
                data.get("code"), oid, root_rpid,
                data.get("message") or data.get("msg") or "",
            )
            break

        page_data = data.get("data", {})
        replies = page_data.get("replies", [])
        if not replies:
            break

        for r in replies:
            all_replies.append(_parse_comment(r, oid))

        page_info = page_data.get("page", {})
        total = page_info.get("count", 0)
        current = page_info.get("num", page)
        per_page = page_info.get("size", PAGE_SIZE)
        if total > 0 and current * per_page >= total:
            break

    return all_replies


def _make_headers(cookie: str, user_agent: str) -> dict[str, str]:
    return {
        "Cookie": cookie,
        "User-Agent": user_agent,
        "Referer": "https://www.bilibili.com/",
    }


def _parse_comment(r: dict[str, Any], oid: str) -> dict[str, Any]:
    return {
        "rpid": str(r.get("rpid", "")),
        "oid": oid,
        "uid": str(r.get("mid", "")),
        "uname": r.get("member", {}).get("uname", ""),
        "avatar_url": r.get("member", {}).get("avatar", ""),
        "parent_rpid": str(r.get("parent", 0)) if r.get("parent", 0) != 0 else "",
        "root_rpid": str(r.get("root", 0)) if r.get("root", 0) != 0 else "",
        "content": r.get("content", {}).get("message", ""),
        "like_count": r.get("like", 0),
        "reply_count": r.get("rcount", 0),
        "publish_at": str(r.get("ctime", "")),
    }
