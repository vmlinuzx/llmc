# Search & Discovery

<!-- TODO: Phase 3a will flesh this out -->

LLMC provides powerful search capabilities that combine semantic understanding with traditional keyword search.

---

## In This Section

- [Semantic Search](semantic-search.md) — Natural language queries
- [Graph Navigation](graph-navigation.md) — where-used, lineage
- [Advanced Queries](advanced-queries.md) — Tips and tricks

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
