#!/usr/bin/env bash
set -euo pipefail

echo "[rg] Checking for ripgrep (rg)"
if command -v rg >/dev/null 2>&1; then
  echo "[rg] Found: $(rg --version | head -n1)"
  exit 0
fi

OS=$(uname -s || echo unknown)
echo "[rg] Not found. Attempting install (OS=$OS)"

if [[ "$OS" == "Linux" ]]; then
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -y && sudo apt-get install -y --no-install-recommends ripgrep
  elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y ripgrep
  elif command -v yum >/dev/null 2>&1; then
    sudo yum install -y ripgrep || sudo yum install -y epel-release && sudo yum install -y ripgrep
  elif command -v pacman >/dev/null 2>&1; then
    sudo pacman -Sy --noconfirm ripgrep
  elif command -v apk >/dev/null 2>&1; then
    sudo apk add --no-cache ripgrep
  else
    echo "I'm sorry I can't do that Dave"
    echo "[rg] No supported package manager found on Linux. Install ripgrep manually: https://github.com/BurntSushi/ripgrep/releases"
    exit 1
  fi
elif [[ "$OS" == "Darwin" ]]; then
  if command -v brew >/dev/null 2>&1; then
    brew install ripgrep
  else
    echo "I'm sorry I can't do that Dave"
    echo "[rg] Homebrew not found. Install Homebrew or install ripgrep manually."
    exit 1
  fi
else
  echo "I'm sorry I can't do that Dave"
  echo "[rg] Unsupported OS for this script. On Windows use: choco install ripgrep or winget install BurntSushi.ripgrep"
  exit 1
fi

if command -v rg >/dev/null 2>&1; then
  echo "[rg] Installed: $(rg --version | head -n1)"
else
  echo "I'm sorry I can't do that Dave"
  echo "[rg] Installation reported success but rg still not found."
  exit 1
fi

