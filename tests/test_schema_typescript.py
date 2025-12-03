"""
Test TypeScript/JavaScript schema extraction.

Validates polyglot RAG support (Roadmap 2.2).
"""

from pathlib import Path
import tempfile
import pytest

from tools.rag.schema import (
    extract_schema_from_file,
    TypeScriptSchemaExtractor,
    Entity,
    Relation,
)


def test_typescript_basic_extraction():
    """Test basic TypeScript entity extraction."""
    ts_code = b"""
import { Handler } from './handler';

export class Router {
  constructor() {
    this.handler = new Handler();
  }
  
  route(req: Request): Response {
    return this.handler.process(req);
  }
}

export function initRouter(): Router {
  const router = new Router();
  return router;
}
"""
    
    with tempfile.NamedTemporaryFile(suffix=".ts", delete=False) as f:
        f.write(ts_code)
        f.flush()
        file_path = Path(f.name)
    
    try:
        entities, relations = extract_schema_from_file(file_path)
        
        # Should extract: Router class, constructor, route method, initRouter function
        assert len(entities) >= 3, f"Expected at least 3 entities, got {len(entities)}"
        
        entity_ids = [e.id for e in entities]
        
        # Check for expected entities
        assert any("Router" in eid for eid in entity_ids), "Router class not found"
        assert any("route" in eid for eid in entity_ids), "route method not found"
        assert any("initRouter" in eid for eid in entity_ids), "initRouter function not found"
        
        # Check entity kinds
        router_entity = next(e for e in entities if "Router" in e.id and e.kind == "class")
        assert router_entity.kind == "class"
        
        init_fn = next(e for e in entities if "initRouter" in e.id)
        assert init_fn.kind == "function"
        
    finally:
        file_path.unlink()


def test_typescript_interfaces_and_types():
    """Test interface and type alias extraction."""
    ts_code = b"""
export interface Config {
  port: number;
  host: string;
}

export type RouteHandler = (req: Request) => Response;

interface Internal {
  id: string;
}
"""
    
    with tempfile.NamedTemporaryFile(suffix=".ts", delete=False) as f:
        f.write(ts_code)
        f.flush()
        file_path = Path(f.name)
    
    try:
        entities, relations = extract_schema_from_file(file_path)
        
        entity_ids = [e.id for e in entities]
        
        # Check for interfaces
        assert any("Config" in eid for eid in entity_ids), "Config interface not found"
        assert any("Internal" in eid for eid in entity_ids), "Internal interface not found"
        
        # Check for type alias
        assert any("RouteHandler" in eid for eid in entity_ids), "RouteHandler type not found"
        
        # Check kinds
        config_entity = next(e for e in entities if "Config" in e.id)
        assert config_entity.kind == "interface"
        
        handler_entity = next(e for e in entities if "RouteHandler" in e.id)
        assert handler_entity.kind == "type"
        
    finally:
        file_path.unlink()


def test_typescript_relations_imports():
    """Test import relation extraction."""
    ts_code = b"""
import { Handler } from './handler';
import { Request, Response } from './types';

export class Router {
  route(req: Request): Response {
    const handler = new Handler();
    return handler.process(req);
  }
}
"""
    
    with tempfile.NamedTemporaryFile(suffix=".ts", delete=False) as f:
        f.write(ts_code)
        f.flush()
        file_path = Path(f.name)
    
    try:
        entities, relations = extract_schema_from_file(file_path)
        
        # Should have call relations
        assert len(relations) > 0, "Expected at least one relation"
        
        # Check for calls relation (new Handler, handler.process)
        call_relations = [r for r in relations if r.edge == "calls"]
        assert len(call_relations) > 0, "Expected call relations"
        
    finally:
        file_path.unlink()


def test_typescript_class_inheritance():
    """Test class inheritance extraction."""
    ts_code = b"""
class BaseRouter {
  handle() {}
}

export class Router extends BaseRouter {
  route() {
    this.handle();
  }
}
"""
    
    with tempfile.NamedTemporaryFile(suffix=".ts", delete=False) as f:
        f.write(ts_code)
        f.flush()
        file_path = Path(f.name)
    
    try:
        entities, relations = extract_schema_from_file(file_path)
        
        # Check for extends relation
        extends_relations = [r for r in relations if r.edge == "extends"]
        assert len(extends_relations) > 0, "Expected extends relation"
        
        # Verify the extends relation points correctly
        router_extends = next(
            r for r in extends_relations 
            if "Router" in r.src and "BaseRouter" in r.dst
        )
        assert router_extends is not None
        
    finally:
        file_path.unlink()


def test_javascript_support():
    """Test that JavaScript files are also supported."""
    js_code = b"""
export class Handler {
  process(req) {
    return { status: 200 };
  }
}

export function createHandler() {
  return new Handler();
}
"""
    
    with tempfile.NamedTemporaryFile(suffix=".js", delete=False) as f:
        f.write(js_code)
        f.flush()
        file_path = Path(f.name)
    
    try:
        entities, relations = extract_schema_from_file(file_path)
        
        # Should extract Handler class and createHandler function
        entity_ids = [e.id for e in entities]
        assert any("Handler" in eid for eid in entity_ids), "Handler class not found"
        assert any("createHandler" in eid for eid in entity_ids), "createHandler function not found"
        
    finally:
        file_path.unlink()


def test_entity_metadata():
    """Test that entities have proper metadata and location tracking."""
    ts_code = b"""
export function greet(name: string, age: number): string {
  return `Hello ${name}`;
}
"""
    
    with tempfile.NamedTemporaryFile(suffix=".ts", delete=False) as f:
        f.write(ts_code)
        f.flush()
        file_path = Path(f.name)
    
    try:
        entities, relations = extract_schema_from_file(file_path)
        
        greet_entity = next(e for e in entities if "greet" in e.id)
        
        # Check metadata
        assert "params" in greet_entity.metadata
        assert len(greet_entity.metadata["params"]) == 2
        
        # Check location tracking
        assert greet_entity.file_path is not None
        assert greet_entity.start_line is not None
        assert greet_entity.end_line is not None
        assert greet_entity.span_hash is not None
        
    finally:
        file_path.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
