"""配置加载与校验模块。"""

import json
import os
from dataclasses import dataclass, field


@dataclass
class Target:
    uid: str
    name: str = ""


@dataclass
class BilibiliConfig:
    cookie: str
    user_agent: str


@dataclass
class FeishuConfig:
    webhook_url: str = ""


@dataclass
class SchedulerConfig:
    interval_minutes: int = 5


@dataclass
class AppConfig:
    bilibili: BilibiliConfig
    feishu: FeishuConfig
    targets: list[Target] = field(default_factory=list)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)


def load_config(config_path: str = "config.json") -> AppConfig:
    """加载并校验配置文件。"""
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"配置文件 {config_path} 不存在，请先创建配置文件。"
        )

    with open(config_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # 校验 bilibili
    if "bilibili" not in raw:
        raise ValueError("配置文件缺少 bilibili 字段")
    bl = raw["bilibili"]
    if not bl.get("cookie") or "你的SESSDATA" in bl["cookie"]:
        raise ValueError("bilibili.cookie 未配置，请填入你的B站完整Cookie")
    if not bl.get("user_agent"):
        raise ValueError("bilibili.user_agent 未配置")

    bilibili = BilibiliConfig(
        cookie=bl["cookie"],
        user_agent=bl["user_agent"],
    )

    # 校验 feishu（可选）
    fs = raw.get("feishu", {})
    webhook_url = fs.get("webhook_url", "")
    feishu = FeishuConfig(webhook_url=webhook_url)

    # 校验 targets
    if "targets" not in raw or not raw["targets"]:
        raise ValueError("targets 未配置，请至少添加一个监控目标")
    targets = []
    for t in raw["targets"]:
        if not t.get("uid"):
            raise ValueError("targets 中某项缺少 uid")
        targets.append(Target(uid=str(t["uid"]), name=t.get("name", "")))

    # 校验 scheduler
    sch = raw.get("scheduler", {})
    interval = sch.get("interval_minutes", 5)
    if not isinstance(interval, int) or interval < 5:
        raise ValueError("scheduler.interval_minutes 必须 >= 5 分钟")

    scheduler = SchedulerConfig(interval_minutes=interval)

    return AppConfig(
        bilibili=bilibili,
        feishu=feishu,
        targets=targets,
        scheduler=scheduler,
    )
