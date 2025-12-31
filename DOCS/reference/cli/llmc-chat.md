# llmc-chat

Chat agent CLI (also: bx)

**Module:** `llmc_agent.cli`

## Usage

```text
Usage: python -m llmc_agent.cli [OPTIONS] [PROMPT_WORDS]...

  bx - AI coding assistant with RAG and tools.

  Examples:
      bx where is the routing logic       Ask about code
      bx read the config and explain it   Use tools to read files
      bx tell me more about that          Continue conversation

  Sessions:
      bx -n start fresh topic             New session (forgets context)
      bx -r                               Recall last exchange
      bx -l                               List recent sessions
      bx -s abc123 continue here          Resume specific session

Options:
  -n, --new           Start a new session
  -r, --recall        Show last exchange
  -l, --list          List recent sessions
  -s, --session TEXT  Use specific session
  --config TEXT       Config file path
  --status            Show status
  --json              JSON output
  -q, --quiet         Suppress metadata
  --no-rag            Disable RAG search
  --no-session        Disable session (stateless mode)
  --model TEXT        Override model
  --no-tools          Disable tools (Crawl-only mode)
  -v, --verbose       Show model thinking
  --version           Show version
  --help              Show this message and exit.
```
