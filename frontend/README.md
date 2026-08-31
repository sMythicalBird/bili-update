# bili-update 前端

在 Windows 上首次使用项目，可以从项目根目录运行 `scripts\init.bat`。脚本会检查并安装 uv、Python 3.12、Node.js LTS、pnpm，并安装前后端依赖。

也可以手动执行：

```bash
pnpm install
pnpm run dev
```

开发服务器默认访问 `http://localhost:5173`，`/api` 请求代理到后端 `http://127.0.0.1:5000`。

先在后端启动 API：

```bash
cd ../backend
uv run python -m src.main --web
```

生产构建使用 `npm run build`，将 `dist` 部署到任意静态服务器即可。
