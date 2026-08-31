"""定时调度模块。"""

import logging
import sqlite3
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler

from src.bilibili.client import fetch_dynamics, fetch_dynamic_detail
from src.config.loader import AppConfig
from src.db import repository
from src.feishu.push import push_dynamics, push_comments
from src.service.sync import update_comments_for_dynamic, update_comments_for_dynamic_collect

logger = logging.getLogger(__name__)


def run_check(config: AppConfig, conn: sqlite3.Connection) -> None:
    """执行一次检查：发现新动态 -> 归档 -> 推送飞书。"""
    logger.info("=" * 50)
    logger.info("开始检查动态 - %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    total_new = 0

    for target in config.targets:
        uid = target.uid
        name = target.name or f"UID:{uid}"

        logger.info("检查 %s...", name)

        dynamics = fetch_dynamics(
            cookie=config.bilibili.cookie,
            user_agent=config.bilibili.user_agent,
            uid=uid,
        )

        if not dynamics:
            logger.info("  %s 无动态或拉取失败", name)
            continue

        new_dynamics = []
        for d in dynamics:
            if repository.dynamic_exists(conn, d["id"]):
                continue
            d["uid"] = uid
            d.setdefault("author_name", name)
            new_dynamics.append(d)

        if not new_dynamics:
            logger.info("  %s 无新动态 (列表共 %d 条)", name, len(dynamics))
            continue

        logger.info("  %s 发现 %d 条新动态，正在处理...", name, len(new_dynamics))

        for d in new_dynamics:
            # 补全正文详情
            if not d["text"]:
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

            repository.upsert_dynamic(conn, d, force_text=False)
            total_new += 1

            # 拉取评论
            update_comments_for_dynamic(config, conn, d)

        # 推送飞书
        push_dynamics(config.feishu.webhook_url, new_dynamics)

    # 每轮检查当天动态的评论，只推送由监控目标用户发布的新评论。
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    watched_uids = {target.uid for target in config.targets}
    new_comments: list[dict] = []
    for target in config.targets:
        for dynamic in repository.get_dynamics(conn, uid=target.uid, limit=1000):
            try:
                published = datetime.fromisoformat(dynamic.get("publish_at", "")).astimezone(ZoneInfo("Asia/Shanghai")).date()
            except (ValueError, TypeError):
                continue
            if published == today:
                new_comments.extend(update_comments_for_dynamic_collect(config, conn, dynamic, watched_uids))
    push_comments(config.feishu.webhook_url, new_comments)
    if new_comments:
        logger.info("本轮发现关注用户新评论 %d 条", len(new_comments))

    logger.info("检查完成，本次共入库 %d 条新动态", total_new)


def create_scheduler(config: AppConfig, conn: sqlite3.Connection) -> BlockingScheduler:
    """创建并配置调度器。"""
    scheduler = BlockingScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(
        run_check,
        trigger="interval",
        minutes=config.scheduler.interval_minutes,
        args=[config, conn],
        id="bili_check",
        name="B站动态检查",
        next_run_time=datetime.now(ZoneInfo("Asia/Shanghai")),
        max_instances=1,
        coalesce=True,
    )
    return scheduler
