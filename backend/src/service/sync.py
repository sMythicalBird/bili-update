"""同步业务逻辑：全量同步、单条更新、评论拉取。"""

import logging
import sqlite3
import time

from src.bilibili.client import fetch_dynamics, fetch_dynamic_detail
from src.bilibili.comment import fetch_comments, fetch_sub_replies
from src.config.loader import AppConfig
from src.db import repository

logger = logging.getLogger(__name__)


def sync_all(
    config: AppConfig,
    conn: sqlite3.Connection,
    force_text: bool = False,
    fetch_comments: bool = True,
) -> dict:
    """全量同步：遍历监控目标，拉取当前动态列表，每条都入库/更新。

    Args:
        config: 应用配置
        conn: 数据库连接
        force_text: True 时强制覆盖正文；False 时仅补空正文
        fetch_comments: 是否同时拉取评论

    Returns:
        统计结果 {"added": int, "updated": int, "comments": int}
    """
    stats = {"added": 0, "updated": 0, "comments": 0}

    for target in config.targets:
        uid = target.uid
        name = target.name or f"UID:{uid}"

        logger.info("同步 %s (UID=%s)...", name, uid)

        dynamics = fetch_dynamics(
            cookie=config.bilibili.cookie,
            user_agent=config.bilibili.user_agent,
            uid=uid,
        )

        if not dynamics:
            logger.warning("  %s 无动态或拉取失败", name)
            continue

        logger.info("  拉到 %d 条动态，逐条处理...", len(dynamics))

        for d in dynamics:
            d["uid"] = uid
            d.setdefault("author_name", name)

            is_new = not repository.dynamic_exists(conn, d["id"])

            # 补全正文详情（列表接口可能为空）
            if not d["text"] or force_text:
                detail = fetch_dynamic_detail(
                    cookie=config.bilibili.cookie,
                    user_agent=config.bilibili.user_agent,
                    dynamic_id=d["id"],
                )
                if detail:
                    d["text"] = detail["text"]
                    d["pics"] = detail["pics"] or d["pics"]
                    d["rid_str"] = d.get("rid_str", "") or detail.get("rid_str", "")
                    d["comment_type"] = detail.get("comment_type", d.get("comment_type", 1))
                    d["publish_at"] = d.get("publish_at", "") or detail.get("publish_at", "")
                time.sleep(0.3)

            repository.upsert_dynamic(conn, d, force_text=force_text)

            if is_new:
                stats["added"] += 1
            else:
                stats["updated"] += 1

            # 拉评论
            if fetch_comments:
                n = update_comments_for_dynamic(config, conn, d)
                stats["comments"] += n

    logger.info(
        "全量同步完成: 新增 %d, 更新 %d, 评论 %d",
        stats["added"], stats["updated"], stats["comments"],
    )
    return stats


def update_dynamic(
    config: AppConfig,
    conn: sqlite3.Connection,
    dynamic_id: str,
    fetch_comments: bool = False,
) -> dict | None:
    """单条更新动态正文（强制刷新）。

    Args:
        config: 应用配置
        conn: 数据库连接
        dynamic_id: 动态 ID
        fetch_comments: 是否顺带拉评论

    Returns:
        更新后的动态 dict，或 None（动态已删除/拉取失败）
    """
    detail = fetch_dynamic_detail(
        cookie=config.bilibili.cookie,
        user_agent=config.bilibili.user_agent,
        dynamic_id=dynamic_id,
    )
    if detail is None:
        logger.warning("动态 %s 拉取失败（可能已删除）", dynamic_id)
        return None

    existing = repository.get_dynamic(conn, dynamic_id)
    if existing is None:
        logger.warning("动态 %s 不在库中，跳过更新", dynamic_id)
        return None

    dynamic = {
        "id": dynamic_id,
        "uid": existing["uid"],
        "type": detail.get("type", existing.get("type", "")),
        "text": detail.get("text", ""),
        "pics": detail.get("pics", []),
        "publish_at": detail.get("publish_at", existing.get("publish_at", "")),
        "url": existing.get("url", ""),
        "rid_str": detail.get("rid_str", "") or existing.get("rid_str", ""),
        "comment_type": detail.get("comment_type", existing.get("comment_type", 1)),
        "article_id": detail.get("article_id", existing.get("article_id", "")),
        "article_content": detail.get("article_content", existing.get("article_content", "")),
        "author_name": detail.get("author_name", existing.get("author_name", "")),
    }

    repository.upsert_dynamic(conn, dynamic, force_text=True)
    logger.info("动态 %s 正文已更新", dynamic_id)

    if fetch_comments:
        update_comments_for_dynamic(config, conn, dynamic)

    return dynamic


def update_comments(
    config: AppConfig,
    conn: sqlite3.Connection,
    dynamic_id: str,
) -> int:
    """单条拉取评论（拉全）。

    Args:
        config: 应用配置
        conn: 数据库连接
        dynamic_id: 动态 ID

    Returns:
        新入库评论数
    """
    dynamic = repository.get_dynamic(conn, dynamic_id)
    if dynamic is None:
        logger.warning("动态 %s 不在库中", dynamic_id)
        return 0

    # 需要 rid_str 才能拉评论
    if not dynamic.get("rid_str"):
        # 尝试通过详情接口补 rid_str
        detail = fetch_dynamic_detail(
            cookie=config.bilibili.cookie,
            user_agent=config.bilibili.user_agent,
            dynamic_id=dynamic_id,
        )
        if detail and detail.get("rid_str"):
            conn.execute(
                "UPDATE dynamics SET rid_str = ?, comment_type = ? WHERE id = ?",
                (detail["rid_str"], detail.get("comment_type", 1), dynamic_id),
            )
            conn.commit()
            dynamic["rid_str"] = detail["rid_str"]
            dynamic["comment_type"] = detail.get("comment_type", 1)
        else:
            logger.warning("动态 %s 无 rid_str，无法拉评论（可能已删除）", dynamic_id)
            return 0

    return update_comments_for_dynamic(config, conn, dynamic)


def update_comments_for_dynamic(
    config: AppConfig,
    conn: sqlite3.Connection,
    dynamic: dict,
) -> int:
    return len(update_comments_for_dynamic_collect(config, conn, dynamic))


def update_comments_for_dynamic_collect(
    config: AppConfig,
    conn: sqlite3.Connection,
    dynamic: dict,
    allowed_uids: set[str] | None = None,
) -> list[dict]:
    """为一条动态拉取并入库全部评论（含楼中楼）。"""
    rid_str = dynamic.get("rid_str", "")
    comment_type = dynamic.get("comment_type", 1)
    dynamic_id = dynamic.get("id", "")

    if not rid_str or not dynamic_id:
        return []

    logger.info("  拉取评论 (rid=%s, type=%d)...", rid_str, comment_type)

    comments = fetch_comments(
        cookie=config.bilibili.cookie,
        user_agent=config.bilibili.user_agent,
        oid=rid_str,
        comment_type=comment_type,
    )

    if not comments:
        logger.info("  无评论")
        return []

    new_comments: list[dict] = []
    for c in comments:
        c["dynamic_id"] = dynamic_id
        if repository.save_comment(conn, c) and (allowed_uids is None or c.get("uid") in allowed_uids):
            new_comments.append(c)

        # 拉子回复
        if c.get("reply_count", 0) > 0:
            sub_replies = fetch_sub_replies(
                cookie=config.bilibili.cookie,
                user_agent=config.bilibili.user_agent,
                oid=rid_str,
                comment_type=comment_type,
                root_rpid=c["rpid"],
            )
            for sr in sub_replies:
                sr["dynamic_id"] = dynamic_id
                if repository.save_comment(conn, sr) and (allowed_uids is None or sr.get("uid") in allowed_uids):
                    new_comments.append(sr)

    logger.info("  评论 %d 条已处理，关注用户新增 %d 条", len(comments), len(new_comments))
    return new_comments
