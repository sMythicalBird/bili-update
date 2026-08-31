#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# uv、pnpm 等用户级工具默认安装在这里；先加入 PATH，避免重复安装。
export PATH="$HOME/.local/bin:$PATH"

# 写入登录配置，保证新终端可以直接找到 uv 和 pnpm；避免重复追加。
for shell_rc in "$HOME/.bashrc" "$HOME/.profile"; do
  touch "$shell_rc"
  grep -qxF 'export PATH="$HOME/.local/bin:$PATH"' "$shell_rc" || \
    printf '\n# bili-update user tools\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$shell_rc"
done

echo "========================================"
echo "bili-update environment initialization"
echo "========================================"

if ! command -v uv >/dev/null 2>&1; then
  echo "[INFO] uv not found. Installing from the official installer..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

if ! command -v node >/dev/null 2>&1; then
  echo "[INFO] Node.js not found. Installing nvm and Node.js LTS..."
  export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
  if [ ! -s "$NVM_DIR/nvm.sh" ]; then
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
  fi
  # shellcheck disable=SC1090
  source "$NVM_DIR/nvm.sh"
  nvm install --lts
  nvm alias default 'lts/*'
fi

mkdir -p "$HOME/.local/bin"
export PATH="$HOME/.local/bin:$PATH"
if ! command -v pnpm >/dev/null 2>&1; then
  echo "[INFO] pnpm not found. Installing it for the current user..."
  npm install --global --prefix "$HOME/.local" pnpm
fi

cd "$ROOT/backend"
echo "[INFO] Installing Python 3.12 and backend dependencies..."
uv python install 3.12
uv sync

cd "$ROOT/frontend"
echo "[INFO] Installing frontend dependencies..."
pnpm install

echo
echo "Initialization complete. Run: ./scripts/start.sh"
