# Implementation Plan: Multi-Platform Packaging

**Branch:** `feature/packaging`  
**Started:** 2025-12-11  
**Status:** 🚧 In Progress

---

## Goal

Make LLMC installable via every major package manager. Zero friction adoption.

---

## Packaging Checklist

### Phase 1: Python Ecosystem (Today)
- [ ] **1.1** Fix package name: `llmcwrapper` → `llmc` (if available on PyPI)
- [ ] **1.2** Update version to 0.6.5
- [ ] **1.3** Build and publish to PyPI
- [ ] **1.4** Add GitHub Actions for auto-publish on release
- [ ] **1.5** Test: `pip install llmc && llmc --version`

### Phase 2: Docker (Today)
- [ ] **2.1** Create `Dockerfile` (multi-stage, slim)
- [ ] **2.2** Create `docker-compose.yml` for local dev
- [ ] **2.3** Push to GitHub Container Registry (ghcr.io)
- [ ] **2.4** Test: `docker run ghcr.io/vmlinuzx/llmc --version`

### Phase 3: Install Script (Today)
- [ ] **3.1** Create `install.sh` (curl-able)
- [ ] **3.2** Host on GitHub Pages or raw.githubusercontent.com
- [ ] **3.3** Test: `curl -sSL https://raw.githubusercontent.com/vmlinuzx/llmc/main/install.sh | bash`

### Phase 4: Homebrew (Quick)
- [ ] **4.1** Create `homebrew-llmc` tap repo
- [ ] **4.2** Write formula
- [ ] **4.3** Test: `brew install vmlinuzx/llmc/llmc`

### Phase 5: AUR (Arch Linux)
- [ ] **5.1** Create PKGBUILD
- [ ] **5.2** Submit to AUR
- [ ] **5.3** Test: `yay -S llmc`

### Phase 6: GitHub Releases (Binaries)
- [ ] **6.1** Set up PyInstaller for single-file binaries
- [ ] **6.2** Add to GitHub Actions release workflow
- [ ] **6.3** Linux x86_64, macOS arm64/x86_64

---

## Install Methods After Completion

```bash
# Python (universal)
pip install llmc
pipx install llmc

# Docker (zero dependencies)
docker run -v $(pwd):/repo ghcr.io/vmlinuzx/llmc index

# One-liner
curl -sSL https://llmc.dev/install.sh | bash

# Homebrew (Mac/Linux)
brew install vmlinuzx/llmc/llmc

# Arch Linux
yay -S llmc

# Direct binary (no Python needed)
wget https://github.com/vmlinuzx/llmc/releases/latest/download/llmc-linux-x86_64
chmod +x llmc-linux-x86_64 && sudo mv llmc-linux-x86_64 /usr/local/bin/llmc
```

---

## Notes

- Skip RPM/DEB for now (high maintenance, low ROI)
- Skip Snap/Flatpak (overkill for dev tools)
