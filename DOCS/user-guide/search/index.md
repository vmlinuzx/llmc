# Search & Discovery

<!-- TODO: Phase 3a will flesh this out -->

LLMC provides powerful search capabilities that combine semantic understanding with traditional keyword search.

---

## In This Section

---

## Quick Examples

```bash
# Basic semantic search
llmc-cli search "authentication middleware"

# Where is this function used?
llmc-cli nav where-used handle_request

# What does this function depend on?
llmc-cli nav lineage DatabasePool
```

---

## See Also

- [CLI Reference](../cli-reference.md) — Full command documentation
- [Configuration](../configuration.md) — Search tuning options
