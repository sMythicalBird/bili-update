"""bili-update - B站动态归档 & 飞书推送。

用法:
    python -m src.main                       # 启动定时调度
    python -m src.main --once                # 检查新动态并推送
    python -m src.main --sync                # 全量同步（补空正文）
    python -m src.main --sync --force        # 全量同步（强制覆盖正文）
    python -m src.main --update <动态ID>      # 单条更新正文
    python -m src.main --update-comments <动态ID>  # 单条拉评论
"""

import argparse
import logging
import sys

from src.config.loader import load_config
from src.db.models import init_db
from src.scheduler.runner import create_scheduler, run_check
from src.service.sync import sync_all, update_dynamic, update_comments

DEFAULT_DB_PATH = "data/bili-update.db"


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    logging.basicConfig(level=level, format=fmt, datefmt=datefmt)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="B站动态归档 & 飞书推送",
    )
    parser.add_argument("--config", "-c", default="config.json", help="配置文件路径")
    parser.add_argument("--db", "-d", default=DEFAULT_DB_PATH, help="SQLite 数据库路径")
    parser.add_argument("--once", action="store_true", help="检查新动态并推送")
    parser.add_argument("--sync", action="store_true", help="全量同步所有监控目标")
    parser.add_argument("--force", action="store_true", help="配合 --sync，强制覆盖正文")
    parser.add_argument("--update", metavar="ID", help="单条更新正文（指定动态ID）")
    parser.add_argument("--update-comments", metavar="ID", help="单条拉取评论（指定动态ID）")
    parser.add_argument("--verbose", "-v", action="store_true", help="DEBUG 日志")
    parser.add_argument("--web", action="store_true", help="启动前端使用的本地 Web API")
    parser.add_argument("--web-host", default="127.0.0.1", help="Web API 监听地址")
    parser.add_argument("--web-port", type=int, default=5000, help="Web API 监听端口")
    args = parser.parse_args()

    setup_logging(args.verbose)
    logger = logging.getLogger("main")

    try:
        config = load_config(args.config)
    except (FileNotFoundError, ValueError) as e:
        logger.error("配置加载失败: %s", e)
        sys.exit(1)

    logger.info(
        "配置加载成功: %d 个监控目标, 间隔 %d 分钟",
        len(config.targets),
        config.scheduler.interval_minutes,
    )

    conn = init_db(args.db)

    try:
        if args.web:
            from src.web import create_app
            create_app(args.db, args.config).run(host=args.web_host, port=args.web_port)
            return

        if args.update:
            result = update_dynamic(config, conn, args.update, fetch_comments=True)
            if result is None:
                logger.error("更新失败（动态可能已删除或拉取失败）")
                sys.exit(1)
            logger.info("动态 %s 更新完成", args.update)
            return

        if args.update_comments:
            n = update_comments(config, conn, args.update_comments)
            logger.info("动态 %s 评论拉取完成，共 %d 条", args.update_comments, n)
            return

        if args.sync:
            sync_all(config, conn, force_text=args.force, fetch_comments=True)
            return

        if args.once:
            run_check(config, conn)
            return

        # 默认：定时调度
        logger.info("启动定时调度...")
        scheduler = create_scheduler(config, conn)
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("收到退出信号，正在关闭...")
            scheduler.shutdown(wait=False)
            logger.info("已退出")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
