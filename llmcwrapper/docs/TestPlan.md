# Test Plan: llmcwrapper
**Date:** 2025-11-12 19:46  

## Matrix
- Modes: yolo/rag × dry-run on/off
- Providers: anthropic (real), minimax (placeholder)
- Overlays: none/one
- One-offs: --set/--unset + LLMC_SET

## Cases
1) yolo + default + dry-run → OK, no RAG/tools
2) yolo + enable rag via --set → error; OK with --force (warn)
3) rag + rag.enabled=false in profile → error; OK with --force
4) rag + unreachable server → error; OK with --force
5) overlay adjusts provider/model → reflected in output
6) shadow-profile logs telemetry (no user merge)
