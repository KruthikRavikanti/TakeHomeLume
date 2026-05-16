from __future__ import annotations

import argparse

from src.policy.retriever import PolicyRetriever


def main() -> None:
    parser = argparse.ArgumentParser(description="Policy Agent CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    retrieve_parser = subparsers.add_parser("retrieve", help="Retrieve policy sections")
    retrieve_parser.add_argument("query", help="Policy retrieval query")
    retrieve_parser.add_argument("--top-k", type=int, default=8)
    retrieve_parser.add_argument("--no-graph", action="store_true", help="Disable graph expansion")

    args = parser.parse_args()

    if args.command == "retrieve":
        _retrieve(args.query, args.top_k, use_graph_expansion=not args.no_graph)


def _retrieve(query: str, top_k: int, use_graph_expansion: bool) -> None:
    retriever = PolicyRetriever(use_graph_expansion=use_graph_expansion)
    results = retriever.retrieve(query, top_k=top_k)

    try:
        from rich.console import Console

        console = Console()
        console.print("Retrieved policy sections:\n")
        for result in results:
            console.print(f"[bold]{result['section_id']} {result['title']}[/bold]")
            console.print(f"score: {result['score']:.3f}")
            console.print(f"semantic_score: {result['semantic_score']:.3f}")
            console.print(f"keyword_score: {result['keyword_score']:.3f}")
            console.print(f"source: {result['retrieval_source']}")
            console.print(f"relationship: {result['relationship']}")
            if result.get("matched_from"):
                console.print(f"matched_from: {result['matched_from']}")
            if result.get("references"):
                console.print(f"references: {', '.join(result['references'])}")
            console.print(f"preview: {_preview(result['text'])}\n")
    except ImportError:
        print("Retrieved policy sections:\n")
        for result in results:
            print(f"{result['section_id']} {result['title']}")
            print(f"score: {result['score']:.3f}")
            print(f"semantic_score: {result['semantic_score']:.3f}")
            print(f"keyword_score: {result['keyword_score']:.3f}")
            print(f"source: {result['retrieval_source']}")
            print(f"relationship: {result['relationship']}")
            if result.get("matched_from"):
                print(f"matched_from: {result['matched_from']}")
            if result.get("references"):
                print(f"references: {', '.join(result['references'])}")
            print(f"preview: {_preview(result['text'])}\n")


def _preview(text: str, max_length: int = 180) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= max_length:
        return collapsed
    return f"{collapsed[: max_length - 3]}..."


if __name__ == "__main__":
    main()
