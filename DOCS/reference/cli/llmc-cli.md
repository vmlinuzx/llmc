# llmc-cli

Primary CLI for LLMC operations

**Module:** `llmc.main`

## Usage

```text
                                       
 Usage: llmc-cli [OPTIONS] COMMAND     
 [ARGS]...                             
                                       
 LLMC: LLM Cost Compression & RAG      
 Tooling                               
                                       
╭─ Options ───────────────────────────╮
│ --version  -v        Show version   │
│                      and exit.      │
│ --help               Show this      │
│                      message and    │
│                      exit.          │
╰─────────────────────────────────────╯
╭─ Commands ──────────────────────────╮
│ tui         Launch the interactive  │
│             TUI.                    │
│ init        Quick init: create      │
│             .llmc/ workspace and    │
│             llmc.toml only.         │
│ monitor     Monitor service logs    │
│             (alias for 'service     │
│             logs -f').              │
│ chat        AI coding assistant     │
│             with RAG-powered        │
│             context.                │
│ config      Configuration           │
│             management: wizard,     │
│             edit, validation.       │
│ service     Manage RAG service      │
│             daemon                  │
│ repo        Repository management:  │
│             register, bootstrap,    │
│             validate, and manage    │
│             LLMC repos.             │
│ analytics   Analytics, search, and  │
│             graph navigation        │
│ debug       Troubleshooting and     │
│             diagnostic commands     │
│ test        Testing and validation  │
│             commands                │
│ docs        LLMC documentation and  │
│             guides                  │
╰─────────────────────────────────────╯

```
