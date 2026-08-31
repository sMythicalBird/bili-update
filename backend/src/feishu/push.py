"""飞书 Webhook 推送模块。"""

import json
import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

TIMEOUT = 10

TYPE_LABELS: dict[str, str] = {
    "DYNAMIC_TYPE_WORD": "文字动态",
    "DYNAMIC_TYPE_AV": "视频投稿",
    "DYNAMIC_TYPE_DRAW": "图片动态",
    "DYNAMIC_TYPE_FORWARD": "转发动态",
    "DYNAMIC_TYPE_ARTICLE": "专栏文章",
    "DYNAMIC_TYPE_LIVE_RCMD": "直播",
}


def push_dynamics(webhook_url: str, dynamics: list[dict[str, Any]]) -> bool:
    """推送动态到飞书。webhook_url 为空时跳过。"""
    if not webhook_url or not dynamics:
        return True

    grouped: dict[str, list[dict[str, Any]]] = {}
    for d in dynamics:
        name = d.get("author_name", "未知UP主")
        grouped.setdefault(name, []).append(d)

    all_success = True
    for name, items in grouped.items():
        card = _build_card(name, items)
        if not _send_card(webhook_url, card):
            all_success = False
            logger.warning("飞书推送失败: %s (%d 条动态)", name, len(items))

    return all_success


def push_comments(webhook_url: str, comments: list[dict[str, Any]]) -> bool:
    """将关注用户发布的新评论以“评论”标记推送。"""
    if not webhook_url or not comments:
        return True
    elements = [{"tag": "div", "text": {"tag": "lark_md", "content": f"**【评论】** {c.get('uname', '用户')}：{c.get('content', '')[:300]}"}} for c in comments]
    for c in comments:
        elements.append({"tag": "action", "actions": [{"tag": "button", "text": {"tag": "plain_text", "content": "查看动态"}, "type": "primary", "url": f"https://t.bilibili.com/{c.get('dynamic_id', '')}"}]})
    return _send_card(webhook_url, {"msg_type": "interactive", "card": {"header": {"title": {"tag": "plain_text", "content": "[BILI] 关注用户评论更新"}, "template": "green"}, "elements": elements}})


def _build_card(name: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(items)
    header_title = (
        f"[BILI] {name} 发布了 {count} 条新动态"
        if count > 1
        else f"[BILI] {name} 发布了新动态"
    )

    elements: list[dict[str, Any]] = []

    for item in items:
        dyn_type = item.get("type", "")
        type_label = TYPE_LABELS.get(dyn_type, dyn_type)

        text = item.get("text", "")
        if text:
            if len(text) > 200:
                text = text[:200] + "……"
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**【{type_label}】**\n{text}",
                },
            })
        else:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**【{type_label}】**（无文字内容）",
                },
            })

        pics = item.get("pics", [])[:3]
        if pics:
            img_elements: list[dict[str, Any]] = []
            for url in pics:
                img_elements.append({
                    "tag": "img",
                    "img_key": url,
                    "alt": {"tag": "plain_text", "content": ""},
                })
            if len(img_elements) == 1:
                elements.append(img_elements[0])
            else:
                elements.append({
                    "tag": "column_set",
                    "flex_mode": "bisect",
                    "background_style": "default",
                    "columns": [
                        {"tag": "column", "width": "weighted", "weight": 1, "elements": [img]}
                        for img in img_elements
                    ],
                })

        elements.append({
            "tag": "action",
            "actions": [{
                "tag": "button",
                "text": {"tag": "plain_text", "content": "查看详情"},
                "type": "primary",
                "url": item.get("url", "https://t.bilibili.com/"),
            }],
        })

        if item is not items[-1]:
            elements.append({"tag": "hr"})

    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": header_title},
                "template": "blue",
            },
            "elements": elements,
        },
    }


def _send_card(webhook_url: str, card: dict[str, Any]) -> bool:
    try:
        resp = requests.post(
            webhook_url,
            json=card,
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        result = resp.json()
        if result.get("code") != 0:
            logger.error("飞书返回错误: code=%s, msg=%s", result.get("code"), result.get("msg", ""))
            return False
        return True
    except requests.RequestException as e:
        logger.error("飞书请求失败: %s", e)
        return False
