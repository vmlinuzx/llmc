# te

Tool Envelope - intelligent command wrapper

**Module:** `llmc.te.cli`

## Usage

```text
usage: te [-h] [-i] [--handle ID] [--chunk N] [--list-handles] [--stats]
          [--json] [--version]

Tool Envelope - enriched shell commands for LLMs

options:
  -h, --help      show this help message and exit
  -i, --raw       Force raw/pass-through mode (skip enrichment even for known
                  commands)
  --handle ID     Retrieve stored result by handle ID
  --chunk N       Chunk number for paginated handle retrieval (default: 0)
  --list-handles  List all stored result handles
  --stats         Show telemetry statistics
  --json          Output results as JSON
  --version       Show TE version

Examples:
  te grep "pattern" path/          # enriched grep with ranking
  te -i grep "pattern"             # raw grep (no enrichment)
  te ls -la                        # pass-through to bash
  te --list-handles                # show stored results
  
Known enriched commands: grep, cat, find
All other commands pass through to bash with telemetry.
        
```
