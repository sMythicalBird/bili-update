from __future__ import annotations
import hashlib
import mimetypes
from pathlib import Path
from urllib.parse import urlparse
import requests

ALLOWED_HOSTS = {f"i{i}.hdslb.com" for i in range(10)} | {"hdslb.com"}

def cached_image(url: str, root: str | Path = "media") -> tuple[Path, str] | None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in ALLOWED_HOSTS:
        return None
    folder = "avatars" if "/face/" in parsed.path else "dynamic-pics"
    directory = Path(root) / folder
    directory.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(url.encode()).hexdigest()
    suffix = Path(parsed.path).suffix.lower() if Path(parsed.path).suffix.lower() in {".jpg", ".jpeg", ".png", ".gif", ".webp"} else ".img"
    path = directory / f"{digest}{suffix}"
    if path.exists() and path.stat().st_size:
        return path, mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    try:
        r = requests.get(url, headers={"Referer": "https://www.bilibili.com/", "User-Agent": "Mozilla/5.0"}, timeout=15)
        r.raise_for_status()
        content_type = r.headers.get("Content-Type", "").split(";", 1)[0]
        if not content_type.startswith("image/"):
            return None
        path.write_bytes(r.content)
        return path, content_type
    except (requests.RequestException, OSError):
        return None
