"""CLI entrypoint for llmc-rag-nav tools."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Any

from tools.rag_nav import metadata, tool_handlers
from tools.rag.nav_meta import RagResult, RagToolMeta


def _wrap_in_envelope(res: Any) -> dict:
    """Wrap a domain result in a standard RagResult envelope."""
    # Determine status based on source/error (assuming if we got a result, it's OK or FALLBACK)
    status = "OK"
    if getattr(res, "source", "") == "LOCAL_FALLBACK":
        status = "FALLBACK"
    
    # Determine message (e.g. truncation warning)
    message = None
    if getattr(res, "truncated", False):
        message = "Result truncated due to limit."

    meta = RagToolMeta(
        status=status,
        source=getattr(res, "source", "RAG_GRAPH"),
        freshness_state=getattr(res, "freshness_state", "UNKNOWN"),
        message=message
    )
    
    items = getattr(res, "items", [])
    envelope = RagResult(meta=meta, items=items)
    return envelope.to_dict()


def main(argv: Optional[list[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(description="LLMC RAG Navigation CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    # build-graph
    p_build = sub.add_parser("build-graph", help="Build schema graph + index status for a repo")
    p_build.add_argument("--repo", required=True, help="Repository root path")

    # status
    p_status = sub.add_parser("status", help="Show RAG index status")
    p_status.add_argument("--repo", required=True, help="Repository root path")
    p_status.add_argument("--json", action="store_true", help="Output as JSON")

    # search
    p_search = sub.add_parser("search", help="Search code using RAG/Nav")
    p_search.add_argument("--repo", required=True, help="Repository root path")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("--limit", type=int, default=20, help="Max results")
    p_search.add_argument("--json", action="store_true", help="Output as JSON")

    # where-used
    p_used = sub.add_parser("where-used", help="Find usages of a symbol")
    p_used.add_argument("--repo", required=True, help="Repository root path")
    p_used.add_argument("symbol", help="Symbol name")
    p_used.add_argument("--limit", type=int, default=50, help="Max results")
    p_used.add_argument("--json", action="store_true", help="Output as JSON")

    # lineage
    p_lineage = sub.add_parser("lineage", help="Find upstream/downstream lineage")
    p_lineage.add_argument("--repo", required=True, help="Repository root path")
    p_lineage.add_argument("symbol", help="Symbol name")
    p_lineage.add_argument("--direction", choices=["upstream", "downstream", "callers", "callees"], default="downstream")
    p_lineage.add_argument("--limit", type=int, default=50, help="Max results")
    p_lineage.add_argument("--json", action="store_true", help="Output as JSON")

    # stats
    p_stats = sub.add_parser("stats", help="Show graph enrichment statistics")
    p_stats.add_argument("--repo", required=True, help="Repository root path")
    p_stats.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args(argv)

    try:
        repo = Path(args.repo).expanduser().resolve()
        if not repo.exists():
            print(f"Error: repo path does not exist: {repo}", file=sys.stderr)
            return 1

        if args.command == "build-graph":
            status = tool_handlers.build_graph_for_repo(repo)
            print(f"Graph built for {repo}")
            print(f"Status: {status.index_state} ({status.schema_version})")
            return 0

        elif args.command == "status":
            st = metadata.load_status(repo)
            if args.json:
                print(json.dumps(st.to_dict() if st else None, indent=2))
            else:
                if not st:
                    print("No index status found.")
                else:
                    print(f"Repo: {st.repo}")
                    print(f"State: {st.index_state}")
                    print(f"Indexed at: {st.last_indexed_at}")
                    print(f"Commit: {st.last_indexed_commit}")
            return 0

        elif args.command == "stats":
            stats = tool_handlers.tool_rag_stats(repo)
            if args.json:
                print(json.dumps(stats, indent=2))
            else:
                print(f"Total Nodes: {stats['total_nodes']}")
                print(f"Enriched Nodes: {stats['enriched_nodes']}")
                print(f"Coverage: {stats['coverage_pct']:.1f}%")
            return 0

        elif args.command == "search":
            res = tool_handlers.tool_rag_search(str(repo), args.query, limit=args.limit)
            if args.json:
                print(json.dumps(_wrap_in_envelope(res), indent=2))
            else:
                _print_search(res)
            return 0

        elif args.command == "where-used":
            res = tool_handlers.tool_rag_where_used(str(repo), args.symbol, limit=args.limit)
            if args.json:
                print(json.dumps(_wrap_in_envelope(res), indent=2))
            else:
                _print_where_used(res)
            return 0

        elif args.command == "lineage":
            direction = "upstream" if args.direction in ("upstream", "callers") else "downstream"
            res = tool_handlers.tool_rag_lineage(str(repo), args.symbol, direction, limit=args.limit)
            if args.json:
                print(json.dumps(_wrap_in_envelope(res), indent=2))
            else:
                _print_lineage(res)
            return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


def _print_search(res):
    print(f"Search: '{res.query}' (Source: {res.source}, Freshness: {res.freshness_state})")
    if not res.items:
        print("  No results.")
        return
    for i, item in enumerate(res.items, 1):
        enrich_tag = " [ENRICHED]" if item.enrichment else ""
        
        # Phase 4: Content Type Annotation
        type_str = ""
        if item.enrichment and item.enrichment.content_type:
            ct = item.enrichment.content_type
            cl = item.enrichment.content_language
            if cl:
                type_str = f" [TYPE: {ct}, LANG: {cl}]"
            else:
                type_str = f" [TYPE: {ct}]"

        print(f"{i}. {item.file}{enrich_tag}{type_str}")
        
        if item.enrichment:
            if item.enrichment.summary:
                print(f"   💡 Summary: {item.enrichment.summary}")
            if item.enrichment.usage_guide:
                print(f"   📘 Usage:   {item.enrichment.usage_guide}")

        if item.snippet and item.snippet.text:
            print(f"   {item.snippet.text.strip()[:80]}...")


def _print_where_used(res):
    print(f"Where Used: '{res.symbol}' (Source: {res.source}, Freshness: {res.freshness_state})")
    if not res.items:
        print("  No usages found.")
        return
    for i, item in enumerate(res.items, 1):
        enrich_tag = " [ENRICHED]" if item.enrichment else ""
        print(f"{i}. {item.file}{enrich_tag}")
        if item.enrichment:
            if item.enrichment.summary:
                print(f"   💡 Summary: {item.enrichment.summary}")


def _print_lineage(res):
    print(f"Lineage ({res.direction}): '{res.symbol}' (Source: {res.source}, Freshness: {res.freshness_state})")
    if not res.items:
        print("  No lineage found.")
        return
    for i, item in enumerate(res.items, 1):
        enrich_tag = " [ENRICHED]" if item.enrichment else ""
        print(f"{i}. {item.file}{enrich_tag}")
        if item.enrichment:
            if item.enrichment.summary:
                print(f"   💡 Summary: {item.enrichment.summary}")


if __name__ == "__main__":
    raise SystemExit(main())
