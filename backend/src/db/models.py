"""数据库初始化：建表 & 迁移 & 索引。"""

import sqlite3
import logging

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    uid         TEXT PRIMARY KEY,
    name        TEXT NOT NULL DEFAULT '',
    avatar_url  TEXT NOT NULL DEFAULT '',
    updated_at  TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS dynamics (
    id           TEXT PRIMARY KEY,
    uid          TEXT NOT NULL,
    type         TEXT NOT NULL DEFAULT '',
    text         TEXT NOT NULL DEFAULT '',
    publish_at   TEXT NOT NULL DEFAULT '',
    url          TEXT NOT NULL DEFAULT '',
    rid_str      TEXT NOT NULL DEFAULT '',
    comment_type INTEGER NOT NULL DEFAULT 1,
    article_id   TEXT NOT NULL DEFAULT '',
    article_content TEXT NOT NULL DEFAULT '',
    fetched_at   TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (uid) REFERENCES users(uid)
);

CREATE TABLE IF NOT EXISTS dynamic_pics (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    dynamic_id  TEXT NOT NULL,
    url         TEXT NOT NULL DEFAULT '',
    local_path  TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (dynamic_id) REFERENCES dynamics(id)
);

CREATE TABLE IF NOT EXISTS comments (
    rpid        TEXT PRIMARY KEY,
    dynamic_id  TEXT NOT NULL,
    uid         TEXT NOT NULL,
    parent_rpid TEXT NOT NULL DEFAULT '',
    root_rpid   TEXT NOT NULL DEFAULT '',
    content     TEXT NOT NULL DEFAULT '',
    like_count  INTEGER NOT NULL DEFAULT 0,
    reply_count INTEGER NOT NULL DEFAULT 0,
    publish_at  TEXT NOT NULL DEFAULT '',
    fetched_at  TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (dynamic_id) REFERENCES dynamics(id),
    FOREIGN KEY (uid) REFERENCES users(uid)
);

CREATE INDEX IF NOT EXISTS idx_dynamics_uid ON dynamics(uid);
CREATE INDEX IF NOT EXISTS idx_comments_dynamic_id ON comments(dynamic_id);
CREATE INDEX IF NOT EXISTS idx_comments_root_rpid ON comments(root_rpid);
CREATE INDEX IF NOT EXISTS idx_dynamic_pics_dynamic_id ON dynamic_pics(dynamic_id);
"""


def _migrate(conn: sqlite3.Connection) -> None:
    """增量迁移：给已有表补新列。"""
    columns = [row[1] for row in conn.execute("PRAGMA table_info(dynamics)").fetchall()]
    if "rid_str" not in columns:
        conn.execute("ALTER TABLE dynamics ADD COLUMN rid_str TEXT NOT NULL DEFAULT ''")
        logger.info("迁移: dynamics 表新增 rid_str 列")
    if "comment_type" not in columns:
        conn.execute("ALTER TABLE dynamics ADD COLUMN comment_type INTEGER NOT NULL DEFAULT 1")
        logger.info("迁移: dynamics 表新增 comment_type 列")
    if "article_id" not in columns:
        conn.execute("ALTER TABLE dynamics ADD COLUMN article_id TEXT NOT NULL DEFAULT ''")
    if "article_content" not in columns:
        conn.execute("ALTER TABLE dynamics ADD COLUMN article_content TEXT NOT NULL DEFAULT ''")


def init_db(db_path: str) -> sqlite3.Connection:
    """初始化数据库，建表、迁移并返回连接。"""
    import os
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

    # APScheduler 默认在线程池中执行任务；允许该连接被调度线程使用。
    # 当前调度任务串行运行（见 max_instances=1），写入仍由 SQLite/WAL 保护。
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA_SQL)
    _migrate(conn)
    conn.commit()
    logger.info("数据库初始化完成: %s", db_path)
    return conn
