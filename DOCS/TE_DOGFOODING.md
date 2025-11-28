# TE Dogfooding Guide

## Purpose

Temporarily use `te` as your shell wrapper to collect real usage telemetry and identify what commands need enrichment.

**WARNING:** This is for LLMC development only. Do NOT use this as your default shell permanently.

## Quick Start

### Option 1: Shell Alias (Recommended for testing)

Add to your `~/.bashrc` or `~/.zshrc`:

```bash
# TE Dogfooding Mode - Use 'te-mode' to enable
alias te-mode='function _te() { /home/vmlinux/src/llmc/scripts/te "$@"; }; alias ls="_te ls"; alias grep="_te grep"; alias cat="_te cat"; alias find="_te find"; alias git="_te git"; alias pwd="_te pwd"; alias head="_te head"; alias tail="_te tail"; alias less="_te less"; export TE_AGENT_ID="manual-shell"; echo "TE mode enabled. Common commands now use te wrapper."; echo "Run te-analyze to see telemetry."; echo "Run te-mode-off to disable."'

alias te-mode-off='unalias ls grep cat find git pwd head tail less 2>/dev/null; unset -f _te 2>/dev/null; unset TE_AGENT_ID; echo "TE mode disabled."'
```

Then:
```bash
source ~/.bashrc  # or ~/.zshrc
te-mode           # Enable TE wrapper
# Do normal work...
te-mode-off       # Disable when done
```

### Option 2: Shell Function Wrapper (More aggressive)

Add to `~/.bashrc`:

```bash
# TE Dogfooding - wraps ALL commands
te-mode-full() {
    export TE_AGENT_ID="manual-shell"
    export ORIGINAL_PATH="$PATH"
    export PATH="/home/vmlinux/src/llmc/scripts:$PATH"
    
    # Create wrapper scripts
    mkdir -p ~/.te-wrappers
    for cmd in ls grep cat find git pwd head tail less ripgrep rg; do
        echo '#!/bin/bash' > ~/.te-wrappers/$cmd
        echo "exec te $(which $cmd 2>/dev/null || echo $cmd) \"\$@\"" >> ~/.te-wrappers/$cmd
        chmod +x ~/.te-wrappers/$cmd
    done
    
    export PATH="$HOME/.te-wrappers:$PATH"
    echo "TE full mode enabled. ALL common commands use te wrapper."
}

te-mode-off() {
    export PATH="$ORIGINAL_PATH"
    unset TE_AGENT_ID
    unset ORIGINAL_PATH
    rm -rf ~/.te-wrappers
    echo "TE mode disabled."
}
```

### Option 3: Just Use 'te' Manually

Instead of aliases, just manually prepend `te`:

```bash
export TE_AGENT_ID="manual-shell"
te ls -la
te grep "pattern" .
te git status
```

This is the safest approach but requires discipline.

## For Claude Desktop Commander Sessions

Add this to your Claude Desktop system prompt or instructions:

```markdown
When working in /home/vmlinux/src/llmc, prefix shell commands with 'te':

GOOD:
- start_process("cd /home/vmlinux/src/llmc && te ls -la")
- start_process("te grep 'pattern' /path/to/file")
- start_process("te git status")

BAD:
- start_process("cd /home/vmlinux/src/llmc && ls -la")  # No te wrapper
```

Or create a wrapper script for DC to use:

```bash
#!/bin/bash
# File: ~/scripts/dc-with-te
# Desktop Commander wrapper that uses TE

export TE_AGENT_ID="claude-dc"
export TE_SESSION_ID="dc-$(date +%s)"

# If command starts with 'cd', split it
if [[ "$1" == cd* ]]; then
    # Extract cd part and remainder
    cd_part=$(echo "$1" | grep -o '^cd [^;]*')
    remainder=$(echo "$1" | sed 's/^cd [^;]*; *//')
    
    if [ -n "$remainder" ]; then
        eval "$cd_part && te $remainder"
    else
        eval "$cd_part"
    fi
else
    te "$@"
fi
```

Then in Claude: `start_process("~/scripts/dc-with-te 'cd /path && ls -la'")`

## Collecting Telemetry

Once TE mode is active, just work normally. Every command gets logged to `.llmc/te_telemetry.db`.

### Check telemetry:
```bash
cd ~/src/llmc
./scripts/te-analyze summary
./scripts/te-analyze by-command
./scripts/te-analyze candidates --limit 10
```

### Find enrichment priorities:
```bash
# What commands are used most?
./scripts/te-analyze by-command --limit 20

# What commands produce the most output (highest ROI for enrichment)?
./scripts/te-analyze candidates --limit 10

# What's slow?
./scripts/te-analyze slow --limit 10
```

### Raw SQL analysis:
```bash
./scripts/te-analyze query "
SELECT 
    cmd,
    COUNT(*) as calls,
    AVG(output_size) as avg_output,
    SUM(output_size) as total_output
FROM telemetry_events
WHERE mode = 'passthrough'
GROUP BY cmd
ORDER BY total_output DESC
LIMIT 10
"
```

## Workflow

1. **Enable TE mode** (pick one option above)
2. **Work on LLMC for 30-60 minutes** - do normal development tasks
3. **Run analytics:**
   ```bash
   cd ~/src/llmc
   ./scripts/te-analyze candidates --limit 10
   ```
4. **Build enrichment handlers** for top candidates
5. **Disable TE mode** when done
6. **Repeat** - collect more data as you use new handlers

## Safety

- **Disable TE mode when not dogfooding** - it adds ~1-2ms overhead per command
- **TE mode is per-shell** - only affects the terminal where you enable it
- **No system changes** - just shell aliases/functions, easy to undo
- **Telemetry is local** - stored in `.llmc/te_telemetry.db`, never sent anywhere

## Expected Results

After 30-60 minutes of normal work, you should see:
- 50-200 command invocations logged
- Clear patterns on which commands are used most
- Data-driven priority list for enrichment handlers

Example output:
```
[te-analyze] Enrichment Candidates
Commands currently using pass-through that might benefit from enrichment:
Command            Calls   Avg Output   Total Output
-------------------------------------------------------
ls                    45        1.2KB         54.2KB
git                   32        0.8KB         25.6KB
grep                  28        0.3KB          8.4KB
cat                   15        2.1KB         31.5KB
find                   8        0.5KB          4.0KB
```

This tells you: **build `ls` and `git` enrichment first** - they're used most and produce the most output.

## Troubleshooting

**Problem:** TE commands feel slow
- Check: `./scripts/te-analyze slow`
- Solution: TE itself should be <5ms overhead. If commands are >100ms, something else is wrong.

**Problem:** No telemetry being collected
- Check: `ls -la .llmc/te_telemetry.db`
- Check: `echo $TE_AGENT_ID` (should not be empty)
- Check: `./scripts/te pwd` works manually

**Problem:** TE mode won't disable
- Run: `exec bash` (restarts shell cleanly)
- Or: just close terminal and open new one

**Problem:** Commands broken in TE mode
- Run: `te-mode-off` immediately
- Check: `./scripts/te --help` works
- Report: which command broke and how

## Advanced: Per-Project TE Mode

Add to project `.envrc` (if using direnv):

```bash
# .envrc in ~/src/llmc
export TE_AGENT_ID="llmc-dev"
export PATH="/home/vmlinux/src/llmc/scripts:$PATH"

# Auto-wrap common commands
alias ls="te ls"
alias grep="te grep"
alias git="te git"

echo "TE mode active for this project"
```

Then `direnv allow` and TE mode is automatic when in the LLMC directory.
