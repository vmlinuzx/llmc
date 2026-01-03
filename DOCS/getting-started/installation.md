# Installation

This guide covers the installation of LLMC (Large Language Model Compressor). You can install it using our automated script, manually via pip, or set it up for development.

## Prerequisites

Before installing, ensure your system meets the following requirements:

- **Operating System:** Linux (recommended) or macOS. Windows users should use [WSL2](https://learn.microsoft.com/en-us/windows/wsl/install).
- **Python:** Version 3.10 or higher.
- **Tools:** `git`, `curl` (for script install), and `pip`.

To check your Python version:
```bash
python3 --version
```

---

## Quick Install (Recommended)

The easiest way to install LLMC is using the provided installer script. This script handles virtual environment creation and dependency installation for you.

Run the following command in your terminal:

```bash
curl -sSL https://raw.githubusercontent.com/vmlinuzx/llmc/main/install.sh | bash
```

Follow the on-screen prompts to complete the setup. The script may ask to add the installation directory to your system's `PATH`.

---

## Manual Installation (Pip)

If you prefer to manage your own environment or use an existing one, you can install LLMC directly from the repository using `pip`.

### 1. Create a Virtual Environment (Optional but Recommended)

We strongly recommend installing LLMC in a virtual environment to avoid conflicts with other system packages.

```bash
# Create a virtual environment named '.venv'
python3 -m venv .venv

# Activate the environment
source .venv/bin/activate
```

### 2. Install via Pip

Install the package with the standard feature set (RAG, TUI, and Agent support):

```bash
pip install "git+https://github.com/vmlinuzx/llmc.git#egg=llmc[rag,tui,agent]"
```

> **Note:** The package name is `llmc`.

---

## Developer Setup

For contributors or those who want to modify the source code.

### 1. Clone the Repository

```bash
git clone https://github.com/vmlinuzx/llmc.git
cd llmc
```

### 2. Set up the Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install in Editable Mode

Install the package in editable mode with all optional dependencies:

```bash
pip install -e ".[rag,tui,agent,dev]"
```

*(Note: If `dev` extras are not defined in the future, `pip install -e ".[rag,tui,agent]"` is sufficient.)*

---

## Verify Installation

Once installed, verify that the CLI is accessible and working correctly.

Check the version:
```bash
llmc-cli --version
```

You should see output indicating the installed version (e.g., `llmc version 0.7.0`).

You can also view the help menu to see available commands:
```bash
llmc-cli --help
```

---

## Troubleshooting

### "Command not found: llmc-cli"

If you see this error after installation, your installation directory is likely not in your system's `PATH`.

**If you used the Quick Install script:**
Restart your shell or run `source ~/.bashrc` (or `~/.zshrc`) to reload your configuration.

**If you installed via pip (user install):**
Add the user base binary directory to your path.
```bash
export PATH="$HOME/.local/bin:$PATH"
```
Add this line to your shell's profile script (e.g., `.bashrc` or `.zshrc`) to make it permanent.

### "Externally-managed-environment" Error

If you try to install with `pip` on modern Linux distributions without a virtual environment, you might see this error.

**Solution:** Use a virtual environment (see "Manual Installation") or use `pipx`:
```bash
pipx install "git+https://github.com/vmlinuzx/llmc.git#egg=llmcwrapper[rag,tui,agent]"
```

### Permission Errors

Avoid using `sudo pip install`. This can mess up your system permissions. Always use a virtual environment or `pip install --user`.