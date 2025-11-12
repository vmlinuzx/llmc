# Testing Protocol (Template)

Every code change should have a quick verification.

Checklist
- Restart affected service(s) if applicable
- Run a targeted test command for the change
- Check logs for errors
- Optional browser spot check

Examples
- Web route: `lynx -dump http://localhost:3000/page | head -20`
- API: `curl -s http://localhost:3000/api/endpoint | jq`
- Script: `./scripts/some_tool.sh --help`

Skip testing for
- Docs-only edits, comments, or non-functional config changes
