# bili-update

B站动态、评论归档与飞书推送工具。

## 首次初始化

Windows PowerShell：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\scripts\init.bat
```

Linux/macOS：

```bash
chmod +x scripts/*.sh
./scripts/init.sh
```

如果提示 `Permission denied`，说明 Shell 脚本没有执行权限。先运行：

```bash
chmod u+x scripts/*.sh
```

如果提示 `/bin/bash^M: no such file or directory`，说明文件使用了 Windows 换行符，可以转换为 Linux 换行符：

```bash
sed -i 's/\r$//' scripts/*.sh
chmod u+x scripts/*.sh
```

也可以直接通过 Bash 执行初始化脚本，无需执行权限：

```bash
bash scripts/init.sh
```

初始化脚本会安装或检查 uv、Python 3.12、Node.js LTS、pnpm，并安装前后端依赖。

## 配置

复制配置模板：

```text
backend/config.example.json → backend/config.json
```

然后填写 B站 Cookie、监控用户和飞书机器人 Webhook。`backend/config.json` 不会被提交到 Git。

## 启动与停止

Windows：

```powershell
.\scripts\start.ps1
.\scripts\stop.ps1
```

Linux/macOS：

```bash
./scripts/start.sh
./scripts/stop.sh
```

启动后：

```text
前端：http://localhost:5173
API：http://127.0.0.1:5000
```

服务在后台运行，日志位于 `backend/logs/` 和 `frontend/logs/`。
