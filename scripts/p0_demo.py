#!/usr/bin/env python3
import argparse
import os

from llmc.rag import tool_rag_lineage, tool_rag_search, tool_rag_where_used


def main() -> None:
    parser = argparse.ArgumentParser(description="P0 demo: DB→Graph→API smoke")
    parser.add_argument("--repo", required=True, help="Repo root")
    parser.add_argument("--query", default="foo")
    parser.add_argument("--enrich-db", default=None, help="Optional explicit enrichment DB path")
    parser.add_argument("--enable-enrich", action="store_true", help="Enable enrichment attach")
    args = parser.parse_args()

    if args.enable_enrich:
        os.environ["LLMC_ENRICH"] = "1"
        if args.enrich_db:
            os.environ["LLMC_ENRICH_DB"] = args.enrich_db
    else:
        os.environ["LLMC_ENRICH"] = "0"

    repo = args.repo
    search_res = tool_rag_search(repo_root=repo, query=args.query, limit=10)
    where_used_res = tool_rag_where_used(repo_root=repo, symbol=args.query, limit=10)
    lineage_res = tool_rag_lineage(
        repo_root=repo, symbol=args.query, direction="downstream", max_results=10
    )

    def show(name: str, result: object) -> None:
        meta = getattr(result, "meta", None)
        print(f"== {name} ==")
        print(
            "status:",
            getattr(meta, "status", None),
            "source:",
            getattr(result, "source", None),
            "freshness:",
            getattr(result, "freshness_state", None),
        )
        items = getattr(result, "items", []) or []
        print("items:", len(items))
        if items:
            first = items[0]
            enrichment = getattr(first, "enrichment", None)
            if enrichment:
                core = {
                    key: enrichment.get(key) for key in ("summary", "inputs", "outputs", "pitfalls")
                }
                print("enrichment:", core)

    show("search", search_res)
    show("where_used", where_used_res)
    show("lineage", lineage_res)


if __name__ == "__main__":
    main()
