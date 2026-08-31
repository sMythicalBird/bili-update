#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# init.sh 安装的 uv/pnpm 是用户级工具；启动时主动加载，避免依赖当前 Shell 是否刷新。
export PATH="$HOME/.local/bin:$PATH"
if [ -n "${NVM_DIR:-}" ] && [ -s "$NVM_DIR/nvm.sh" ]; then
  # shellcheck disable=SC1090
  source "$NVM_DIR/nvm.sh"
elif [ -s "$HOME/.nvm/nvm.sh" ]; then
  # shellcheck disable=SC1090
  source "$HOME/.nvm/nvm.sh"
fi
RUN_DIR="$ROOT/.run"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
mkdir -p "$RUN_DIR" "$BACKEND/logs" "$FRONTEND/logs"

start_service() {
  local name="$1" dir="$2" log="$3"
  local pid_file="$RUN_DIR/$name.pid"
  if [ -f "$pid_file" ]; then
    local old_pid
    old_pid="$(cat "$pid_file")"
    if kill -0 "$old_pid" 2>/dev/null; then
      echo "$name is already running (PID $old_pid)."
      return
    fi
    rm -f "$pid_file"
  fi
  (cd "$dir" && nohup bash -c "$4" >"$log.out.log" 2>"$log.err.log" </dev/null & echo $! >"$pid_file")
  local pid
  pid="$(cat "$pid_file")"
  echo "$name started (PID $pid)."
}

echo "Starting bili-update in background..."
start_service api "$BACKEND" "$BACKEND/logs/api" 'uv run python -m src.main --web'
start_service scheduler "$BACKEND" "$BACKEND/logs/scheduler" 'uv run python -m src.main'
start_service frontend "$FRONTEND" "$FRONTEND/logs/frontend" 'pnpm run dev --host 127.0.0.1'
api_pid="$(cat "$RUN_DIR/api.pid")"
scheduler_pid="$(cat "$RUN_DIR/scheduler.pid")"
frontend_pid="$(cat "$RUN_DIR/frontend.pid")"

echo
echo "Frontend: http://localhost:5173"
echo "API:      http://127.0.0.1:5000"
echo "PIDs:     api=$api_pid scheduler=$scheduler_pid frontend=$frontend_pid"
echo "Logs:     backend/logs and frontend/logs"
