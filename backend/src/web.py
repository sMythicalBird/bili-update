"""本地 Web API：为前端提供动态、评论和运行配置。"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_file
from flask_cors import CORS

from src.config.loader import load_config
from src.db.models import init_db
from src.db import repository
from src.service.sync import update_comments, update_dynamic
from src.media.cache import cached_image


def create_app(db_path: str = "data/bili-update.db", config_path: str = "config.json") -> Flask:
    app = Flask(__name__)
    CORS(app)
    app.config.update(DB_PATH=db_path, CONFIG_PATH=config_path)

    @app.get("/api/image")
    def image_proxy():
        # send_file 会以 Flask 的 app.root_path 解析相对路径，因此这里统一使用绝对路径。
        media_root = Path(app.config["DB_PATH"]).resolve().parent.parent / "media"
        result = cached_image(request.args.get("url", ""), media_root)
        if result is None:
            return jsonify({"error": "图片不可用或地址不被允许"}), 404
        path, content_type = result
        response = send_file(path, mimetype=content_type, max_age=86400)
        response.headers["Cache-Control"] = "public, max-age=86400"
        return response

    def db() -> sqlite3.Connection:
        conn = sqlite3.connect(app.config["DB_PATH"])
        conn.row_factory = sqlite3.Row
        return conn

    @app.get("/api/health")
    def health():
        conn = db()
        try:
            conn.execute("SELECT 1")
            return jsonify({"ok": True})
        finally:
            conn.close()

    @app.get("/api/users")
    def users():
        conn = db()
        try:
            rows = conn.execute("SELECT uid, name, avatar_url, updated_at FROM users ORDER BY name, uid").fetchall()
            return jsonify([dict(r) for r in rows])
        finally:
            conn.close()

    @app.get("/api/dynamics")
    def dynamics():
        try:
            limit = min(max(int(request.args.get("limit", 20)), 1), 100)
            offset = max(int(request.args.get("offset", 0)), 0)
        except ValueError:
            return jsonify({"error": "limit/offset 必须是数字"}), 400
        uid = request.args.get("uid") or None
        conn = db()
        try:
            items = repository.get_dynamics(conn, uid=uid, limit=limit, offset=offset)
            total = conn.execute("SELECT COUNT(*) FROM dynamics" + (" WHERE uid = ?" if uid else ""), ((uid,) if uid else ())).fetchone()[0]
            for item in items:
                pics = conn.execute("SELECT url, local_path FROM dynamic_pics WHERE dynamic_id = ? ORDER BY id", (item["id"],)).fetchall()
                item["pics"] = [dict(p) for p in pics]
            return jsonify({"items": items, "total": total, "limit": limit, "offset": offset})
        finally:
            conn.close()

    @app.get("/api/dynamics/<dynamic_id>")
    def dynamic_detail(dynamic_id: str):
        conn = db()
        try:
            item = repository.get_dynamic(conn, dynamic_id)
            if not item:
                return jsonify({"error": "动态不存在"}), 404
            item["pics"] = [dict(p) for p in conn.execute("SELECT url, local_path FROM dynamic_pics WHERE dynamic_id = ? ORDER BY id", (dynamic_id,)).fetchall()]
            item["comments"] = repository.get_comments_tree(conn, dynamic_id)
            return jsonify(item)
        finally:
            conn.close()

    @app.post("/api/dynamics/<dynamic_id>/refresh")
    def refresh_dynamic(dynamic_id: str):
        try:
            config = load_config(app.config["CONFIG_PATH"])
            conn = db()
            try:
                result = update_dynamic(config, conn, dynamic_id, fetch_comments=False)
                if result is None:
                    return jsonify({"error": "动态刷新失败或已删除"}), 404
                return jsonify(repository.get_dynamic(conn, dynamic_id))
            finally:
                conn.close()
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.post("/api/dynamics/<dynamic_id>/refresh-comments")
    def refresh_comments(dynamic_id: str):
        try:
            config = load_config(app.config["CONFIG_PATH"])
            conn = db()
            try:
                count = update_comments(config, conn, dynamic_id)
                if not repository.get_dynamic(conn, dynamic_id):
                    return jsonify({"error": "动态不存在"}), 404
                return jsonify({"updated": count, "comments": repository.get_comments_tree(conn, dynamic_id)})
            finally:
                conn.close()
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    @app.get("/api/config")
    def get_config():
        path = Path(app.config["CONFIG_PATH"])
        if not path.exists():
            return jsonify({"error": "配置文件不存在"}), 404
        return jsonify(json.loads(path.read_text(encoding="utf-8")))

    @app.put("/api/config")
    def put_config():
        payload: Any = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "请求体必须是 JSON 对象"}), 400
        temp = Path(str(app.config["CONFIG_PATH"]) + ".tmp")
        try:
            temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            load_config(str(temp))
            os.replace(temp, app.config["CONFIG_PATH"])
            return jsonify({"ok": True})
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            if temp.exists():
                temp.unlink()
            return jsonify({"error": str(exc)}), 400

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=True)
