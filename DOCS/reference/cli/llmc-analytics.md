# llmc analytics

The `llmc analytics` command group handles search, statistics, and graph navigation.

## Commands

### `search`

Perform a semantic search over the index.

```bash
llmc analytics search "query string"
```

### `stats`

Show statistics for the current index.

```bash
llmc analytics stats
```

### `where-used`

Find usages of a symbol.

```bash
llmc analytics where-used symbol_name
```

### `lineage`

Show lineage (upstream/downstream dependencies) for a symbol.

```bash
llmc analytics lineage symbol_name
```
