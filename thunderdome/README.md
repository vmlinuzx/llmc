# Thunderdome

Portable testing infrastructure for LLMC and other repositories.

## Structure

```
thunderdome/
├── agents/           # Testing agent scripts
│   ├── emilia.sh     # Orchestrator - schedules demons, triages findings
│   └── demons/       # Individual testing demons
│       ├── rem_testing.sh  # Ruthless testing (Gemini)
│       └── _template.sh    # Template for new demons
├── lib/              # Shared helpers
│   └── common.sh     # Logging, repo detection, report paths
├── prompts/          # Canonical agent prompts
│   └── rem_testing.md
└── scripts/          # Utilities
    └── migrate_reports.sh
```

## Usage

### Test Current Repository
```bash
./thunderdome/agents/emilia.sh
```

### Test Any Repository
```bash
./thunderdome/agents/emilia.sh --repo /path/to/other/repo
```

### Quick Mode (Security + Gap Only)
```bash
./thunderdome/agents/emilia.sh --quick
```

### Parallel Mode (tmux)
```bash
./thunderdome/agents/emilia.sh --tmux
```

## Reports

Reports are written to the **target repository**, not thunderdome:

```
<target_repo>/tests/REPORTS/
├── current/      # Active test run
├── previous/     # One generation back (auto-rotated)
└── archive/      # Historical reports
```

### Naming Convention
```
{agent}_{scope}_{YYYY-MM-DD}.md
```

Examples:
- `emilia_daily_2025-12-16.md`
- `rem_testing_2025-12-16.md`
- `rem_security_2025-12-16.md`

## Adding New Demons

1. Copy `agents/demons/_template.sh`
2. Update `DEMON_NAME` and `DEMON_SCOPE`
3. Implement your testing logic
4. Register in `emilia.sh` DEMONS array

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `LLMC_TARGET_REPO` | Override target repository |
| `GEMINI_API_KEY` | For Gemini-based demons (Rem) |
| `GEMINI_MODEL` | Model override (default: gemini-2.5-pro) |
