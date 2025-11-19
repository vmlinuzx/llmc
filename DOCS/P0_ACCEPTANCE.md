# P0 Acceptance & Smoke Pack
**Date:** 2025-11-19

This additive patch gives you a fast, decisive **P0 end-to-end acceptance**:
- One **acceptance test** that proves DB→Graph→API wiring for search/where-used/lineage.
- One **demo script** you can run locally to see real output (with or without enrichment).
- Tiny **playbook** with exact commands.

## Apply
```bash
git checkout -b feat/p0-acceptance
git apply --reject --whitespace=fix patches/0001-p0-acceptance-and-smoke.patch
```

