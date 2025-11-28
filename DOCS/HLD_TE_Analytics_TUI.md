# HLD: TE Analytics TUI Enhancements

## Overview
High-level design for enhancing the TE Analytics TUI with better visibility, prioritization, and real-time feedback.

## Current State
- System Summary (top): Total calls, unique commands, enriched %, avg latency, data flow
- Left Panel: Top Unenriched Candidates (command, calls, avg size)
- Right Panel: Top Enriched Actions (currently empty)
- Bottom: Refresh/Back buttons

## Proposed Enhancements

### 1. Top Bar Enhancements

**Add:**
- **Time Range Selector** - buttons/dropdown: `1h | 6h | 24h | 7d | 30d | All`
  - Updates all panels when changed
  - Default: 7d (current behavior)
  - Stored preference remembered between sessions

- **Enriched vs Pass-through Ratio Gauge**
  - Visual progress bar or pie chart
  - Shows `enriched / (enriched + passthrough)` as percentage
  - Color: Gray (0-20%), Yellow (20-50%), Green (50%+)
  - Label: "15 enriched / 85 pass-through (15%)"

**Why:**
- Quick visual KPI of enrichment adoption
- Time range lets you zoom into "last hour of work" vs "all time"

---

### 2. Left Panel: Unenriched Candidates Enhancements

**Add Sort Options (cycle with 's' key or button):**
- `By Calls` (default) - most used first
- `By Total Output` - highest total KB first
- `By Avg Output` - largest avg KB first
- `By Latency` - slowest first

**Add Columns:**
- Current: `Command | Calls | Avg Size`
- New: `Command | Calls | Avg Size | Total Size | Avg Latency | Est. Tokens`

**Estimated Token Cost Column:**
- Formula: `avg_output_bytes / 4` (rough token estimate)
- Shows potential tokens saved if enriched to 20% of original
- Example: `ls: 1.2KB avg = ~300 tokens → ~240 tokens saved if enriched`
- Color code: High ROI (>100 tokens) = Green, Medium (50-100) = Yellow, Low (<50) = Gray

**Sparkline (optional, if room):**
- Tiny graph showing call frequency over time
- Helps identify trending vs stable commands

**Why:**
- Multiple sort views reveal different priorities:
  - By calls: what's used most (volume)
  - By output: what costs most tokens (ROI)
  - By latency: what's slow (UX)
- Token estimates make ROI concrete

---

### 3. Right Panel: Enriched Actions Enhancements

**When enriched commands exist, show:**

**Columns:**
- `Command | Calls | Savings | Latency Impact`

**Savings Metrics:**
- Compare enriched vs pass-through output sizes
- Formula: `(passthrough_avg_size - enriched_avg_size) / passthrough_avg_size * 100`
- Example: `grep: 85% reduction (0.3KB → 0.05KB)`
- Color: Green for high savings (>70%), Yellow (40-70%), Red (<40%)

**Latency Impact:**
- Compare enriched vs pass-through avg latency
- Show as delta: `+2ms`, `-5ms`, `~0ms`
- Color: Green if faster/same, Yellow if <10ms slower, Red if >10ms slower

**Status Indicator:**
- "✓ Working" - enrichment is active and saving tokens
- "⚠ Slow" - enrichment adds >10ms overhead
- "⚠ Unused" - enrichment exists but no recent calls

**Why:**
- Validates that enrichment is worth it
- Identifies enrichment handlers that need optimization
- Celebrates wins ("grep saved 15KB today!")

---

### 4. Bottom Section: Recent Activity Stream

**Replace or add below current panels:**

**Activity Stream Display:**
```
Recent Activity (Last 20 commands)
────────────────────────────────────────────────────────────────
11:15:43  manual-shell    ls -la          pass   2ms    1.2KB
11:15:41  manual-shell    grep "pattern"  pass   3ms    0.3KB
11:15:38  claude-dc       git status      pass   45ms   0.8KB
11:15:32  manual-shell    pwd             pass   1ms    0.03KB
...
```

**Columns:**
- Time (HH:MM:SS or relative "2s ago")
- Agent ID (or "—" if unknown)
- Command (truncated to ~30 chars)
- Mode (pass/enriched/error)
- Latency
- Output Size

**Color Coding:**
- Pass-through: Default/Gray
- Enriched: Green/Cyan
- Error: Red

**Auto-scroll:**
- New commands appear at top
- Auto-refresh every 2-3 seconds if watching live
- Pause scroll on user interaction (arrow keys, etc.)

**Why:**
- Real-time feedback during dogfooding
- See exactly what's being logged
- Spot patterns and anomalies immediately
- Validates that telemetry is working

---

### 5. Bottom Status Bar

**Add persistent status line:**
```
[5 total │ 3 commands │ 1.8ms avg │ 3.8KB total │ DB: 24KB │ Last refresh: 11:15:43]
```

**Fields:**
- Total calls (current time range)
- Unique commands
- Avg latency
- Total output size
- Database file size
- Last refresh timestamp

**Why:**
- Always-visible quick stats
- Database size helps know when to archive/clean
- Timestamp shows if data is fresh

---

### 6. Optional: Command Category Breakdown

**If space allows, add a small sidebar or top metrics:**

**Categories:**
- File Ops: ls, cat, head, tail, find (count + %)
- Git Ops: status, diff, log, commit (count + %)
- Search: grep, rg, ack (count + %)
- Navigation: cd, pwd, pushd, popd (count + %)
- Other: everything else (count + %)

**Display:**
```
Categories:
  File Ops:   15 (30%)  ████████░░
  Git Ops:    12 (24%)  ██████░░░░
  Search:      8 (16%)  ████░░░░░░
  Navigation:  5 (10%)  ██░░░░░░░░
  Other:      10 (20%)  █████░░░░░
```

**Why:**
- Shows usage patterns at a glance
- Helps prioritize enrichment by category
- "Oh, I'm mostly doing git ops, should focus there"

---

## Implementation Priority

**P0 (Must Have):**
1. Time range selector
2. Sort options on Unenriched Candidates
3. Recent Activity Stream
4. Bottom status bar

**P1 (Should Have):**
5. Enriched/Pass-through ratio gauge
6. Estimated token cost column
7. Enriched Actions metrics (when enrichment exists)

**P2 (Nice to Have):**
8. Command category breakdown
9. Sparklines
10. Latency impact visualization

---

## Data Sources

All data comes from `.llmc/te_telemetry.db`:

**Existing queries work:**
- Summary stats: `SELECT COUNT(*), AVG(latency_ms), SUM(output_size) FROM telemetry_events WHERE timestamp >= ?`
- By command: `SELECT cmd, mode, COUNT(*), AVG(output_size), AVG(latency_ms) FROM telemetry_events GROUP BY cmd, mode`
- Recent activity: `SELECT timestamp, agent_id, cmd, mode, latency_ms, output_size FROM telemetry_events ORDER BY id DESC LIMIT 20`

**New queries needed:**
- Time-filtered stats: Add `WHERE timestamp >= ?` with time range
- Savings calculation: Compare `mode='enriched'` vs `mode='passthrough'` for same command
- Category classification: Use regex/lookup table to categorize commands

---

## UI Layout Mockup

```
┌─────────────────────────────────────────────────────────────────────┐
│ TE Analytics :: 11:15:43          [1h|6h|24h|7d|30d|All]  [█15%▒85%]│
├─────────────────────────────────────────────────────────────────────┤
│ System Summary (Last 7 Days)                                        │
│   5 Total │ 3 Unique │ 0.0% Enriched │ 1.8ms Avg │ 3.8KB Flow      │
├──────────────────────────────────────┬──────────────────────────────┤
│ Top Unenriched Candidates [Sort: ▼] │ Top Enriched Actions         │
│                                      │                              │
│ Cmd    Calls  AvgSz  Total  Tokens  │ Cmd    Calls  Savings  Δms  │
│ ───    ─────  ─────  ─────  ──────  │ ───    ─────  ───────  ───  │
│ pwd       2    0.03KB 0.06KB   ~15   │ (none yet)                  │
│ ls        2    1.9KB  3.8KB   ~950   │                             │
│ echo      1    0.0KB  0.0KB     ~0   │                             │
│                                      │                             │
├──────────────────────────────────────┴──────────────────────────────┤
│ Recent Activity (Last 20)                                           │
│ 11:15:43  manual-shell  ls -la           pass   2ms    1.2KB       │
│ 11:15:41  claude-dc     grep "pattern"   pass   3ms    0.3KB       │
│ 11:15:38  manual-shell  git status       pass   45ms   0.8KB       │
├─────────────────────────────────────────────────────────────────────┤
│ [Refresh] [Back]                                                    │
│ 5 total │ 3 cmds │ 1.8ms avg │ 3.8KB │ DB:24KB │ Refresh:11:15:43 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Technical Notes

**Performance:**
- Recent Activity Stream: Use `SELECT ... ORDER BY id DESC LIMIT 20` - stays fast even with 10K+ rows
- Time range filter: Index on `timestamp` column (already exists)
- Auto-refresh: Poll DB every 2-3 seconds only when TUI is visible

**State Management:**
- Remember time range selection between sessions (store in config or temp file)
- Remember sort preference per panel
- Pause auto-refresh when user is interacting (scrolling, etc.)

**Color Scheme:**
- Enriched: Green/Cyan
- Pass-through: Gray/Default
- Error: Red
- High-value (ROI): Green highlights
- Low-value: Dimmed/Gray

**Keyboard Shortcuts:**
- `r` - Refresh now
- `s` - Cycle sort mode
- `t` - Cycle time range
- `↑/↓` - Scroll recent activity
- `q` - Back/Quit

---

## Success Metrics

After implementation, user should be able to:
1. ✅ See what commands are used most (by calls, by output, by latency)
2. ✅ Estimate token savings potential for unenriched commands
3. ✅ Validate enrichment effectiveness (savings, latency impact)
4. ✅ Watch real-time command activity as it happens
5. ✅ Adjust time range to focus on recent work or all-time patterns

**The goal:** Make prioritization and validation **obvious at a glance** instead of requiring mental math or multiple queries.
