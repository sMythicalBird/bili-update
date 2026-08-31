"""快速测试 B站动态拉取，不依赖飞书配置。

用法:
    python -m scripts.test_fetch
或:
    uv run python scripts/test_fetch.py
"""

import json
import logging
import sys

from src.bilibili.client import fetch_dynamics, fetch_dynamic_detail

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

CONFIG_PATH = "config.json"


def main():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    cookie = config["bilibili"]["cookie"]
    user_agent = config["bilibili"]["user_agent"]
    targets = config.get("targets", [])

    if "你的SESSDATA" in cookie:
        print("[ERROR] 请先在 config.json 中填入你的 B站 Cookie")
        return

    if not targets:
        print("[ERROR] config.json 中 targets 为空")
        return

    for target in targets:
        uid = target["uid"]
        name = target.get("name", uid)

        print()
        print("=" * 60)
        print(f"  拉取 {name} (UID={uid}) 的动态...")
        print("=" * 60)

        dynamics = fetch_dynamics(cookie=cookie, user_agent=user_agent, uid=uid)

        if not dynamics:
            print("  [WARN] 未拉取到动态")
            continue

        print(f"  共拉取到 {len(dynamics)} 条动态:")
        print()

        for i, d in enumerate(dynamics, 1):
            if not d["text"]:
                print(f"  正在获取详情 [{i}/{len(dynamics)}]...")
                detail = fetch_dynamic_detail(
                    cookie=cookie, user_agent=user_agent, dynamic_id=d["id"],
                )
                if detail:
                    d["text"] = detail["text"]
                    d["pics"] = detail["pics"] or d["pics"]

            print(f"  [{i}] {d['type']}")
            print(f"      作者: {d['author_name']}")
            print(f"      ID:   {d['id']}")
            text = d["text"]
            if text:
                if len(text) > 500:
                    text = text[:500] + "..."
                print(f"      内容: {text}")
            else:
                print(f"      内容: (无文字)")
            if d["pics"]:
                print(f"      图片: {len(d['pics'])} 张")
            print(f"      链接: {d['url']}")
            print()


if __name__ == "__main__":
    main()
