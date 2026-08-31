"""B站动态 API 客户端，带 Cookie 鉴权。"""

import logging
import json
import re
import time
from datetime import datetime, timezone
from typing import Any

import requests

logger = logging.getLogger(__name__)

API_FEED_SPACE = "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space"
API_DETAIL = "https://api.bilibili.com/x/polymer/web-dynamic/v1/detail"
API_ARTICLE = "https://api.bilibili.com/x/article/view"
DYNAMIC_URL_TEMPLATE = "https://t.bilibili.com/{dynamic_id}"
TIMEOUT = 15


def fetch_dynamics(
    cookie: str,
    user_agent: str,
    uid: str,
    max_retries: int = 2,
) -> list[dict[str, Any]]:
    """拉取指定用户的最新动态列表（仅列表，不含详情文字）。"""
    headers = _make_headers(cookie, user_agent, uid)
    items = _fetch_feed(headers, uid, max_retries)
    return [_parse_item(item) for item in items]


def fetch_dynamic_detail(
    cookie: str,
    user_agent: str,
    dynamic_id: str,
    max_retries: int = 1,
) -> dict[str, Any] | None:
    """拉取单条动态的详情。

    Returns:
        {"text", "pics", "rid_str", "comment_type", "publish_at", "author_name", "type"}
        或 None（动态已删除/不可访问）
    """
    headers = _make_headers(cookie, user_agent, "")
    result = _fetch_detail(headers, dynamic_id, max_retries)
    if result and result.get("article_id"):
        article = _fetch_article(headers, result["article_id"])
        if article:
            result["article_content"] = article.get("content", "")
            result["text"] = article.get("title", "") + ("\n" + article.get("content", "") if article.get("content") else "")
        # 粉丝/充电专享文章的 API 可能只返回 App 提示，PC /opus 页面仍含完整正文。
        if not result.get("article_content") or "App" in result.get("article_content", ""):
            page_text = _fetch_opus_content(headers, dynamic_id)
            if page_text:
                result["article_content"] = page_text
                result["text"] = page_text
    return result


def _fetch_opus_content(headers: dict[str, str], dynamic_id: str) -> str:
    """从 PC 端 opus 页面内嵌的 INITIAL_STATE 提取文章段落。"""
    try:
        response = requests.get(f"https://www.bilibili.com/opus/{dynamic_id}", headers=headers, timeout=TIMEOUT)
        response.raise_for_status()
        marker = "window.__INITIAL_STATE__="
        start = response.text.find(marker)
        if start < 0:
            return ""
        state, _ = json.JSONDecoder().raw_decode(response.text[start + len(marker):])
        paragraphs: list[str] = []
        for module in (state.get("detail", {}).get("modules", []) or []):
            content = module.get("module_content") or {}
            for paragraph in content.get("paragraphs", []) or []:
                text = paragraph.get("text") or {}
                for node in text.get("nodes", []) or []:
                    word = node.get("word") or {}
                    value = word.get("words", "")
                    if value:
                        paragraphs.append(value)
        return "\n\n".join(paragraphs)
    except (requests.RequestException, ValueError, TypeError, KeyError):
        logger.debug("解析 opus 页面正文失败 (id=%s)", dynamic_id, exc_info=True)
        return ""


def _fetch_article(headers: dict[str, str], article_id: str) -> dict[str, Any] | None:
    try:
        response = requests.get(API_ARTICLE, params={"id": article_id}, headers=headers, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()
        return data.get("data") if data.get("code") == 0 else None
    except (requests.RequestException, ValueError):
        return None


def _make_headers(cookie: str, user_agent: str, uid: str) -> dict[str, str]:
    return {
        "Cookie": cookie,
        "User-Agent": user_agent,
        "Referer": f"https://space.bilibili.com/{uid}/" if uid else "https://www.bilibili.com/",
    }


def _fetch_feed(
    headers: dict[str, str],
    uid: str,
    max_retries: int,
) -> list[dict[str, Any]]:
    params = {"host_mid": uid, "offset": ""}

    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(
                API_FEED_SPACE, params=params, headers=headers, timeout=TIMEOUT,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            if attempt < max_retries:
                logger.warning("请求失败，1秒后重试 (%d/%d): %s", attempt + 1, max_retries, e)
                time.sleep(1)
                continue
            logger.error("拉取动态列表失败 (UID=%s): %s", uid, e)
            return []

        data = resp.json()
        code = data.get("code", -1)
        if code != 0:
            _handle_error_code(code, uid)
            return []

        items = data.get("data", {}).get("items", [])
        if items:
            return items

        if attempt < max_retries:
            logger.warning("API 返回空结果，0.5秒后重试 (%d/%d)", attempt + 1, max_retries)
            time.sleep(0.5)
            continue

        logger.info("UID=%s 暂无动态", uid)
        return []

    return []


def _fetch_detail(
    headers: dict[str, str],
    dynamic_id: str,
    max_retries: int,
) -> dict[str, Any] | None:
    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(
                API_DETAIL, params={"id": dynamic_id}, headers=headers, timeout=TIMEOUT,
            )
            resp.raise_for_status()
            break
        except requests.RequestException as e:
            if attempt < max_retries:
                time.sleep(1)
            else:
                logger.warning("拉取详情失败 (id=%s): %s", dynamic_id, e)
                return None

    data = resp.json()
    if data.get("code") != 0:
        return None

    item = data.get("data", {}).get("item", {})
    modules = item.get("modules", {})
    md = modules.get("module_dynamic", {})

    # 正文
    desc = md.get("desc") or {}
    text = desc.get("text", "")

    # 图片
    major = md.get("major") or {}
    pics: list[str] = []
    opus = major.get("opus") or {}
    for pic in opus.get("pics", []):
        url = pic.get("url", "")
        if url:
            pics.append(url)
    if not pics:
        draw = major.get("draw") or {}
        for item_pic in draw.get("items", []):
            url = item_pic.get("src", "")
            if url:
                pics.append(url)

    # 专栏文章动态：正文摘要和标题位于 major.article
    article = major.get("article") or {}
    article_id = str(article.get("id", ""))
    if not text and article:
        title = article.get("title", "")
        summary = article.get("desc", "")
        text = "\n".join(part for part in (title, summary) if part)
    if not pics and article:
        pics.extend(article.get("covers") or [])

    # 评论相关字段
    basic = item.get("basic", {})
    rid_str = basic.get("rid_str", "")
    comment_type = basic.get("comment_type", 1)

    # 作者
    author = modules.get("module_author", {})
    author_name = author.get("name", "")

    # 发布时间
    pub_ts = author.get("pub_ts", "")
    publish_at = ""
    if pub_ts:
        try:
            publish_at = datetime.fromtimestamp(
                int(pub_ts), tz=timezone.utc
            ).isoformat()
        except (ValueError, OSError):
            pass

    return {
        "text": text,
        "pics": pics,
        "rid_str": rid_str,
        "comment_type": comment_type,
        "author_name": author_name,
        "publish_at": publish_at,
        "type": item.get("type", ""),
        "article_id": article_id,
        "article_content": "",
    }


def _handle_error_code(code: int, uid: str) -> None:
    messages = {
        -101: f"Cookie 已失效，请重新获取 (UID={uid})",
        -412: f"请求被拦截/限流，请稍后再试 (UID={uid})",
    }
    msg = messages.get(code, f"B站 API 返回错误 code={code} (UID={uid})")
    logger.warning(msg)


def _parse_item(item: dict[str, Any]) -> dict[str, Any]:
    """将列表接口返回的原始动态项转换为标准格式。"""
    id_str = item.get("id_str", "")

    modules = item.get("modules", {})
    author = modules.get("module_author", {})
    author_name = author.get("name", "")

    basic = item.get("basic", {})
    rid_str = basic.get("rid_str", "")
    comment_type = basic.get("comment_type", 1)

    dynamic = modules.get("module_dynamic", {})
    major = dynamic.get("major") or {}

    text = ""
    desc = dynamic.get("desc") or {}
    if desc:
        text = desc.get("text", "")
    if not text:
        opus = major.get("opus") or {}
        if opus:
            summary = opus.get("summary") or {}
            text = summary.get("text", "")

    article = major.get("article") or {}
    article_id = str(article.get("id", ""))
    if not text and article:
        title = article.get("title", "")
        summary = article.get("desc", "")
        text = "\n".join(part for part in (title, summary) if part)

    pics: list[str] = []
    opus = major.get("opus") or {}
    for pic in opus.get("pics", []):
        url = pic.get("url", "")
        if url:
            pics.append(url)
    if not pics:
        article = major.get("article") or {}
        pics.extend(article.get("covers") or [])

    pub_ts = author.get("pub_ts", "")
    publish_at = ""
    if pub_ts:
        try:
            publish_at = datetime.fromtimestamp(
                int(pub_ts), tz=timezone.utc
            ).isoformat()
        except (ValueError, OSError):
            pass

    return {
        "id": id_str,
        "type": item.get("type", ""),
        "rid_str": rid_str,
        "comment_type": comment_type,
        "author_name": author_name,
        "text": text,
        "pics": pics,
        "publish_at": publish_at,
        "url": DYNAMIC_URL_TEMPLATE.format(dynamic_id=id_str),
        "article_id": article_id,
        "article_content": "",
    }
