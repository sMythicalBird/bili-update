"""查看数据库内容。用法: uv run python scripts/query_db.py [tables|users|comments]"""

import os
import sqlite3
import sys
from datetime import datetime, timezone, timedelta

DB_PATH = "data/bili-update.db"
TZ_SHANGHAI = timezone(timedelta(hours=8))


def _check_db():
    if not os.path.exists(DB_PATH):
        print(f"数据库文件不存在: {DB_PATH}")
        print("请先运行: uv run python -m src.main --once")
        sys.exit(0)


def _to_local(iso_str):
    if not iso_str:
        return "(无)"
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        local = dt.astimezone(TZ_SHANGHAI)
        return local.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return iso_str


def show_dynamics():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, type, text, publish_at, fetched_at, url FROM dynamics ORDER BY fetched_at DESC"
    ).fetchall()
    print(f"\n=== 动态 ({len(rows)} 条) ===")
    for r in rows:
        print(f"\n  ID: {r['id']}")
        print(f"  类型: {r['type']}")
        print(f"  发布时间: {_to_local(r['publish_at'])}")
        print(f"  入库时间: {_to_local(r['fetched_at'])}")
        text = r["text"] or "(无文字)"
        print(f"  内容: {text}")
        print(f"  链接: {r['url']}")
    conn.close()


def show_users():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT uid, name FROM users").fetchall()
    print(f"\n=== 用户 ({len(rows)} 个) ===")
    for r in rows:
        print(f"  {r['uid']}  {r['name']}")
    conn.close()


def show_comments(dynamic_id=""):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    if dynamic_id:
        rows = conn.execute(
            """SELECT c.*, u.name as uname
               FROM comments c LEFT JOIN users u ON c.uid = u.uid
               WHERE c.dynamic_id = ?
               ORDER BY c.publish_at ASC""",
            (dynamic_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT c.*, u.name as uname
               FROM comments c LEFT JOIN users u ON c.uid = u.uid
               ORDER BY c.dynamic_id, c.publish_at ASC LIMIT 50"""
        ).fetchall()

    print(f"\n=== 评论 ({len(rows)} 条) ===")
    for r in rows:
        parent = f" <- {r['parent_rpid'][:16]}" if r["parent_rpid"] else ""
        indent = "    " if r["parent_rpid"] else ""
        print(f"{indent}[{r['dynamic_id'][:20]}...] {r['uname']}: {r['content'][:80]}{parent}")
    conn.close()


def show_tables():
    conn = sqlite3.connect(DB_PATH)
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    print("=== 表 ===")
    for t in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM [{t[0]}]").fetchone()[0]
        print(f"  {t[0]}: {count} 行")
    conn.close()


if __name__ == "__main__":
    _check_db()
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "users":
        show_users()
    elif arg == "comments":
        show_comments(sys.argv[2] if len(sys.argv) > 2 else "")
    elif arg == "tables":
        show_tables()
    else:
        show_tables()
        show_dynamics()
