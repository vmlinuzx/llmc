"""
End-to-end integration test for TypeScript schema extraction.

This test creates a small TypeScript project and verifies that:
1. Entities are extracted (classes, functions, interfaces)
2. Relations are tracked (imports, calls, extends)
3. The schema graph can be built and saved
4. All expected symbols appear in the graph
"""

import json
from pathlib import Path
import tempfile

from tools.rag.schema import build_schema_graph


def test_typescript_repo_integration():
    """Test end-to-end schema graph building for a TypeScript project."""
    
    # Create a temporary directory for our test project
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        
        # Create a mini TypeScript project structure
        src_dir = repo_root / "src"
        src_dir.mkdir()
        
        # File 1: types.ts
        types_file = src_dir / "types.ts"
        types_file.write_text("""
export interface Request {
  path: string;
  method: string;
}

export interface Response {
  status: number;
  body: string;
}

export type RouteHandler = (req: Request) => Response;
""")
        
        # File 2: handler.ts
        handler_file = src_dir / "handler.ts"
        handler_file.write_text("""
import { Request, Response } from './types';

export class Handler {
  process(req: Request): Response {
    return {
      status: 200,
      body: 'OK'
    };
  }
  
  logRequest(req: Request): void {
    console.log(req.path);
  }
}
""")
        
        # File 3: router.ts
        router_file = src_dir / "router.ts"
        router_file.write_text("""
import { Handler } from './handler';
import { Request, Response } from './types';

export class Router {
  private handler: Handler;
  
  constructor() {
    this.handler = new Handler();
  }
  
  route(req: Request): Response {
    this.handler.logRequest(req);
    return this.handler.process(req);
  }
}

export function createRouter(): Router {
  return new Router();
}
""")
        
        # Build the schema graph
        file_paths = list(src_dir.glob("*.ts"))
        graph = build_schema_graph(repo_root, file_paths)
        
        # ===== Verify entities =====
        entity_ids = [e.id for e in graph.entities]
        
        # Check for types
        assert any("Request" in eid for eid in entity_ids), "Request interface not found"
        assert any("Response" in eid for eid in entity_ids), "Response interface not found"
        assert any("RouteHandler" in eid for eid in entity_ids), "RouteHandler type not found"
        
        # Check for classes
        assert any("Handler" in eid for eid in entity_ids), "Handler class not found"
        assert any("Router" in eid for eid in entity_ids), "Router class not found"
        
        # Check for methods
        assert any("process" in eid for eid in entity_ids), "Handler.process not found"
        assert any("route" in eid for eid in entity_ids), "Router.route not found"
        assert any("logRequest" in eid for eid in entity_ids), "Handler.logRequest not found"
        
        # Check for functions
        assert any("createRouter" in eid for eid in entity_ids), "createRouter function not found"
        
        # ===== Verify entity details =====
        handler_class = next(e for e in graph.entities if "Handler" in e.id and e.kind == "class")
        assert handler_class.file_path is not None
        assert "handler.ts" in handler_class.file_path
        assert handler_class.start_line is not None
        assert handler_class.end_line is not None
        
        # ===== Verify relations =====
        [(r.src, r.edge, r.dst) for r in graph.relations]
        
        # Check for call relations
        # Router.route should call Handler.process and Handler.logRequest
        route_calls = [r for r in graph.relations if "route" in r.src and r.edge == "calls"]
        assert len(route_calls) >= 2, f"Expected at least 2 calls from route, got {len(route_calls)}"
        
        # ===== Verify graph can be serialized =====
        graph_dict = graph.to_dict()
        assert "entities" in graph_dict
        assert "relations" in graph_dict
        assert len(graph_dict["entities"]) > 0
        assert len(graph_dict["relations"]) > 0
        
        # Test saving and loading
        output_file = repo_root / "schema.json"
        graph.save(output_file)
        assert output_file.exists()
        
        # Verify JSON structure
        with open(output_file) as f:
            loaded_data = json.load(f)
            assert "version" in loaded_data
            assert "entities" in loaded_data
            assert "relations" in loaded_data
        
        print(f"✅ Successfully extracted {len(graph.entities)} entities and {len(graph.relations)} relations")
        print(f"   Entities: {', '.join(e.id[:40] for e in graph.entities[:5])}...")
        print(f"   Relations: {len([r for r in graph.relations if r.edge == 'calls'])} calls, "
              f"{len([r for r in graph.relations if r.edge == 'extends'])} extends")


if __name__ == "__main__":
    test_typescript_repo_integration()
    print("\n🎉 Integration test passed!")
