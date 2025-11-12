# install_ripgrep.sh — Install `rg` with Friendly Messages

Path
- scripts/install_ripgrep.sh

Purpose
- Detect and install ripgrep (`rg`) using the platform’s package manager with Beatrice‑style guardrails.

Usage
- `scripts/install_ripgrep.sh`

Behavior
- Supports `apt`, `dnf`, `yum`, `pacman`, `apk`, or Homebrew on macOS. Prints a polite refusal with manual instructions when it can’t proceed.

