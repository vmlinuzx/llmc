# Reference

Lookup documentation for LLMC APIs, commands, and configuration.

---

## Reference Sections

| Section | Description | Status |
|---------|-------------|--------|
| [CLI Commands](cli/index.md) | Complete command-line reference | Generated |
| [Configuration](config/index.md) | llmc.toml schema reference | Generated |
| [MCP Tools](mcp-tools/index.md) | MCP tool documentation | Generated |
| [API](api/index.md) | Internal API documentation | Generated |

---

## Generation

Reference docs are auto-generated from source code. To regenerate:

```bash
make docs-gen
```

Or manually:

```bash
python scripts/generate_cli_docs.py
python scripts/generate_config_docs.py
python scripts/generate_mcp_docs.py
```

---

## Note

These documents are generated. Do not edit manually — your changes will be overwritten.
