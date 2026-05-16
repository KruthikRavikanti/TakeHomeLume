from __future__ import annotations

from rich.console import Console

from src.policy.retriever import PolicyRetriever, parse_policy_sections


def main() -> None:
    console = Console()
    sections = parse_policy_sections()
    retriever = PolicyRetriever()
    graph = retriever.graph
    parent_child_edges = sum(len(section["children"]) for section in sections)
    reference_edges = sum(len(section["references"]) for section in sections)

    console.print(f"Parsed sections: {len(sections)}")
    console.print(f"Graph nodes: {len(graph.by_id)}")
    console.print(f"Parent-child edges: {parent_child_edges}")
    console.print(f"Cross-reference edges: {reference_edges}")
    console.print(f"Embedding model: {retriever.embedding_model_name}")
    console.print(f"BM25 index built: {retriever.bm25 is not None}")
    console.print("Sample sections:")
    for section in sections[:8]:
        console.print(
            f"- {section['section_id']} {section['title']} "
            f"parent={section['parent_id']} "
            f"children={section['children'][:4]} "
            f"references={section['references'][:4]}"
        )


if __name__ == "__main__":
    main()
