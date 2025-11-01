# Key Directory Structure (Template)

repo/
├─ app/                # or src/ — application
├─ components/         # UI components
├─ services/           # API/integration clients
├─ scripts/            # dev tools & orchestration
│  ├─ codex_wrap.sh    # routing wrapper
│  ├─ llm_gateway.*    # local-first LLM gateway
│  └─ sync_to_drive.sh # background drive sync
├─ DOCS/               # documentation
└─ tests/              # automated tests

Guidelines
- Keep directories shallow and purposeful
- Avoid deep cross-dependencies
- Group scripts by purpose under `scripts/`
