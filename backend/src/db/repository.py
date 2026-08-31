"""数据操作层：增删改查。"""

import sqlite3
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def dynamic_exists(conn: sqlite3.Connection, dynamic_id: str) -> bool:
    """判断动态是否已入库。"""
    row = conn.execute(
        "SELECT 1 FROM dynamics WHERE id = ?", (dynamic_id,)
    ).fetchone()
    return row is not None


def get_dynamic(conn: sqlite3.Connection, dynamic_id: str) -> dict[str, Any] | None:
    """查询单条动态，含 UP主信息。"""
    row = conn.execute(
        """SELECT d.*, u.name as author_name, u.avatar_url as author_avatar
           FROM dynamics d LEFT JOIN users u ON d.uid = u.uid
           WHERE d.id = ?""",
        (dynamic_id,),
    ).fetchone()
    return _row_to_dict(row) if row else None


def upsert_dynamic(
    conn: sqlite3.Connection,
    dynamic: dict[str, Any],
    force_text: bool = False,
) -> None:
    """新增或更新一条动态。

    Args:
        conn: 数据库连接
        dynamic: 动态数据，含 id, uid, type, text, publish_at, url,
                 rid_str, comment_type, pics, author_name, author_avatar
        force_text: True 时强制覆盖正文；False 时正文为空才补
    """
    now = datetime.now(timezone.utc).isoformat()

    # 保存 UP主
    _upsert_user(
        conn,
        uid=dynamic["uid"],
        name=dynamic.get("author_name", ""),
        avatar_url=dynamic.get("author_avatar", ""),
    )

    new_text = dynamic.get("text", "")
    rid_str = dynamic.get("rid_str", "")
    comment_type = dynamic.get("comment_type", 1)

    existing = get_dynamic(conn, dynamic["id"])

    if existing is None:
        # 新增
        conn.execute(
            """INSERT INTO dynamics
               (id, uid, type, text, publish_at, url, rid_str, comment_type, article_id, article_content, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                dynamic["id"],
                dynamic["uid"],
                dynamic.get("type", ""),
                new_text,
                dynamic.get("publish_at", ""),
                dynamic.get("url", ""),
                rid_str,
                comment_type,
                dynamic.get("article_id", ""), dynamic.get("article_content", ""),
                now,
            ),
        )
    else:
        # 更新：正文策略
        if force_text and new_text:
            final_text = new_text
        elif not existing.get("text") and new_text:
            final_text = new_text
        else:
            final_text = existing.get("text", "")

        # rid_str / comment_type 优先用新拉到的（旧的为空时补）
        final_rid = rid_str or existing.get("rid_str", "")
        final_ctype = comment_type if rid_str else existing.get("comment_type", 1)

        conn.execute(
            """UPDATE dynamics
               SET text = ?, rid_str = ?, comment_type = ?, article_id = COALESCE(NULLIF(?, ''), article_id), article_content = COALESCE(NULLIF(?, ''), article_content), fetched_at = ?
               WHERE id = ?""",
            (final_text, final_rid, final_ctype, dynamic.get("article_id", ""), dynamic.get("article_content", ""), now, dynamic["id"]),
        )

    # 保存配图（去重：先删后插，简单可靠）
    if dynamic.get("pics"):
        conn.execute("DELETE FROM dynamic_pics WHERE dynamic_id = ?", (dynamic["id"],))
        for pic_url in dynamic["pics"]:
            conn.execute(
                "INSERT INTO dynamic_pics (dynamic_id, url) VALUES (?, ?)",
                (dynamic["id"], pic_url),
            )

    conn.commit()
    logger.debug("动态已入库/更新: %s", dynamic["id"])


def save_dynamic(conn: sqlite3.Connection, dynamic: dict[str, Any]) -> None:
    """保存一条动态（兼容旧接口，等于 upsert 且补空正文）。"""
    upsert_dynamic(conn, dynamic, force_text=False)


def save_user(conn: sqlite3.Connection, uid: str, name: str, avatar_url: str) -> None:
    """保存或更新用户信息。"""
    _upsert_user(conn, uid, name, avatar_url)
    conn.commit()


def save_comment(conn: sqlite3.Connection, comment: dict[str, Any]) -> bool:
    """保存一条评论（INSERT OR IGNORE 去重）。"""
    now = datetime.now(timezone.utc).isoformat()

    _upsert_user(
        conn,
        uid=comment["uid"],
        name=comment.get("uname", ""),
        avatar_url=comment.get("avatar_url", ""),
    )

    cursor = conn.execute(
        """INSERT OR IGNORE INTO comments
           (rpid, dynamic_id, uid, parent_rpid, root_rpid,
            content, like_count, reply_count, publish_at, fetched_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            comment["rpid"],
            comment.get("dynamic_id", ""),
            comment["uid"],
            comment.get("parent_rpid", ""),
            comment.get("root_rpid", ""),
            comment.get("content", ""),
            comment.get("like_count", 0),
            comment.get("reply_count", 0),
            comment.get("publish_at", ""),
            now,
        ),
    )

    conn.commit()
    logger.debug("评论已入库: %s", comment["rpid"])
    return cursor.rowcount > 0


def get_dynamics(
    conn: sqlite3.Connection,
    uid: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """查询动态列表，按 publish_at 倒序（最新的在前）。"""
    if uid:
        rows = conn.execute(
            """SELECT d.*, u.name as author_name, u.avatar_url as author_avatar
               FROM dynamics d LEFT JOIN users u ON d.uid = u.uid
               WHERE d.uid = ? ORDER BY d.publish_at DESC LIMIT ? OFFSET ?""",
            (uid, limit, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT d.*, u.name as author_name, u.avatar_url as author_avatar
               FROM dynamics d LEFT JOIN users u ON d.uid = u.uid
               ORDER BY d.publish_at DESC LIMIT ? OFFSET ?""",
            (limit, offset),
        ).fetchall()

    return [_row_to_dict(row) for row in rows]


def get_comments(
    conn: sqlite3.Connection,
    dynamic_id: str,
) -> list[dict[str, Any]]:
    """查询某条动态的所有评论（扁平列表）。"""
    rows = conn.execute(
        """SELECT c.*, u.name as uname, u.avatar_url
           FROM comments c LEFT JOIN users u ON c.uid = u.uid
           WHERE c.dynamic_id = ?
           ORDER BY c.publish_at ASC""",
        (dynamic_id,),
    ).fetchall()
    return [_row_to_dict(row) for row in rows]


def get_comments_tree(
    conn: sqlite3.Connection,
    dynamic_id: str,
) -> list[dict[str, Any]]:
    """查询某条动态的评论，构造成楼中楼树形结构（供 UI 用）。

    返回结构:
    [
        {
            "rpid": ..., "content": ..., "uname": ..., ...,
            "children": [ { 子回复 }, ... ]
        },
        ...
    ]
    """
    comments = get_comments(conn, dynamic_id)
    by_id: dict[str, dict[str, Any]] = {}
    roots: list[dict[str, Any]] = []

    for c in comments:
        c["children"] = []
        by_id[c["rpid"]] = c

    for c in comments:
        root = c.get("root_rpid", "")
        if root and root in by_id:
            by_id[root]["children"].append(c)
        else:
            # 一级评论（无 root）或 root 不在本页
            roots.append(c)

    return roots


def get_all_dynamic_ids(conn: sqlite3.Connection) -> list[str]:
    """获取库里所有动态 ID。"""
    rows = conn.execute("SELECT id FROM dynamics").fetchall()
    return [r[0] for r in rows]


def _upsert_user(
    conn: sqlite3.Connection,
    uid: str,
    name: str,
    avatar_url: str,
) -> None:
    """插入或更新用户信息。"""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO users (uid, name, avatar_url, updated_at)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(uid) DO UPDATE SET
               name = COALESCE(NULLIF(excluded.name, ''), name),
               avatar_url = COALESCE(NULLIF(excluded.avatar_url, ''), avatar_url),
               updated_at = excluded.updated_at""",
        (uid, name, avatar_url, now),
    )


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)
