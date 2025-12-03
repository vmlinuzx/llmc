# Mini-SDD: Polyglot RAG Support (Roadmap 2.2)

**Author:** Otto (Claude Opus 4.5)  
**Date:** 2025-12-02  
**Status:** Ready  
**Effort:** 6-8 hours  
**Difficulty:** 🟡 Medium

---

## Goal

Make schema extraction work for JavaScript/TypeScript, using existing tree-sitter infrastructure.

---

## Current State

**What exists:**
```
lang.py          → tree-sitter parsing for JS/TS/Go/Rust/etc (DONE)
database.py      → slice_language, content_language fields (DONE)
schema.py        → Entity/Relation/SchemaGraph model (DONE, language-agnostic)
                 → PythonSchemaExtractor using ast module (DONE)
                 → extract_schema_from_file() - Python only (NEEDS WORK)
```

**The gap:** `PythonSchemaExtractor` is the only extractor. It uses Python's `ast` module, not tree-sitter.

---

## Design

### Option A: TreeSitter-Based Extractors (Recommended)

Create language-specific extractors that use tree-sitter queries:

```python
# schema.py additions

class TreeSitterSchemaExtractor:
    """Base class for tree-sitter based extraction."""
    
    def __init__(self, file_path: Path, source: bytes, lang: str):
        self.file_path = file_path
        self.source = source
        self.lang = lang
        self.tree = parse_source(lang, source)  # from lang.py
    
    def extract(self) -> tuple[list[Entity], list[Relation]]:
        raise NotImplementedError


class TypeScriptSchemaExtractor(TreeSitterSchemaExtractor):
    """Extract entities from TypeScript/JavaScript."""
    
    # Node types to extract
    FUNCTION_NODES = {"function_declaration", "arrow_function", "method_definition"}
    CLASS_NODES = {"class_declaration"}
    EXPORT_NODES = {"export_statement"}
    IMPORT_NODES = {"import_statement"}
    
    def extract(self) -> tuple[list[Entity], list[Relation]]:
        entities, relations = [], []
        self._walk(self.tree, entities, relations)
        return entities, relations
    
    def _walk(self, node: Node, entities: list, relations: list):
        if node.type in self.FUNCTION_NODES:
            entities.append(self._extract_function(node))
        elif node.type in self.CLASS_NODES:
            entities.append(self._extract_class(node))
        # ... etc
        
        for child in node.children:
            self._walk(child, entities, relations)
```

### Wire Into extract_schema_from_file()

```python
def extract_schema_from_file(file_path: Path) -> tuple[list[Entity], list[Relation]]:
    lang = language_for_path(file_path)
    source = file_path.read_bytes()
    
    if lang == "python":
        extractor = PythonSchemaExtractor(file_path, source.decode())
    elif lang in ("typescript", "javascript", "tsx"):
        extractor = TypeScriptSchemaExtractor(file_path, source, lang)
    else:
        return [], []  # Unsupported language
    
    return extractor.extract()
```

---

## Entity Mapping: TypeScript → Graph

| TS Construct | Entity Kind | Example |
|--------------|-------------|---------|
| `function foo()` | function | `sym:foo` |
| `const foo = () => {}` | function | `sym:foo` |
| `class Foo {}` | class | `sym:Foo` |
| `interface Foo {}` | interface | `sym:Foo` |
| `type Foo = ...` | type | `sym:Foo` |
| `export { foo }` | (relation) | export edge |

## Relation Mapping

| TS Construct | Relation Edge |
|--------------|---------------|
| `import { foo } from './bar'` | imports |
| `foo()` inside function | calls |
| `extends BaseClass` | extends |
| `implements Interface` | implements |
| `new Foo()` | instantiates |

---

## Tree-Sitter Node Types (Reference)

Key node types for TypeScript extraction:

```
# Functions
function_declaration      → function foo() {}
arrow_function            → const foo = () => {}
method_definition         → class { foo() {} }

# Classes & Types  
class_declaration         → class Foo {}
interface_declaration     → interface Foo {}
type_alias_declaration    → type Foo = ...

# Imports/Exports
import_statement          → import { x } from 'y'
export_statement          → export { x }
export_default_declaration

# Calls
call_expression           → foo(), new Bar()
member_expression         → obj.method
```

---

## Implementation Plan

### Phase 1: Base Infrastructure (2h)
- [ ] Create `TreeSitterSchemaExtractor` base class
- [ ] Add `TypeScriptSchemaExtractor` skeleton
- [ ] Wire language dispatch in `extract_schema_from_file()`
- [ ] Test: empty extractor doesn't crash on .ts files

### Phase 2: Entity Extraction (2-3h)
- [ ] Extract functions (regular, arrow, methods)
- [ ] Extract classes
- [ ] Extract interfaces and type aliases
- [ ] Extract exports (named, default)
- [ ] Test: entities appear in graph for sample TS repo

### Phase 3: Relation Extraction (2-3h)
- [ ] Extract imports → `imports` relation
- [ ] Extract function calls → `calls` relation  
- [ ] Extract class extends → `extends` relation
- [ ] Extract new expressions → `instantiates` relation
- [ ] Test: `where-used` and `lineage` work for TS symbols

### Phase 4: Integration (1h)
- [ ] Update `_discover_source_files()` to include .ts/.tsx/.js/.jsx
- [ ] Run full index on a real TS repo (e.g., small React app)
- [ ] Verify RAG search returns TS results
- [ ] Update docs

---

## Files to Modify

```
tools/rag/schema.py
├── TreeSitterSchemaExtractor (new base class)
├── TypeScriptSchemaExtractor (new)
└── extract_schema_from_file() (add dispatch)

tools/rag/lang.py
└── (already done - no changes needed)

tests/
└── test_schema_typescript.py (new)
```

---

## Test Repo

Use a minimal TS repo for testing:

```typescript
// src/router.ts
import { Handler } from './handler';

export class Router {
  private handler: Handler;
  
  constructor() {
    this.handler = new Handler();
  }
  
  route(req: Request): Response {
    return this.handler.process(req);
  }
}

// src/handler.ts
export class Handler {
  process(req: Request): Response {
    return new Response('ok');
  }
}
```

Expected graph:
- Entities: `Router`, `Handler`, `route`, `process`, `constructor`
- Relations: `Router→imports→Handler`, `Router→instantiates→Handler`, `route→calls→process`

---

## Success Criteria

1. `llmc index` on a TS repo produces entities in the graph
2. `llmc nav where-used Handler` shows callers
3. `llmc nav lineage Router` shows dependency tree
4. `llmc search "router"` returns TS results with symbols

---

## Future (Not This PR)

- Go extractor
- Rust extractor
- Java extractor
- Cross-language relations (Python calling TS via subprocess, etc.)
