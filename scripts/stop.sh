#!/usr/bin/env bash
set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT/.run"

kill_tree() {
  local pid="$1"
  local child
  for child in $(pgrep -P "$pid" 2>/dev/null || true); do
    kill_tree "$child"
  done
  kill "$pid" 2>/dev/null || true
}

stopped=0
for name in api scheduler frontend; do
  pid_file="$RUN_DIR/$name.pid"
  [ -f "$pid_file" ] || continue
  pid="$(cat "$pid_file")"
  if [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null; then
    kill_tree "$pid"
    echo "$name stopped (PID $pid)."
    stopped=1
  fi
  rm -f "$pid_file"
done

if [ "$stopped" -eq 0 ]; then
  echo "No bili-update processes were recorded as running."
fi
