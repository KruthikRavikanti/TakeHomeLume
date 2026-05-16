from __future__ import annotations

import argparse
import json
from uuid import uuid4

from src.intent import extract_intent
from src.llm.client import get_default_llm_client
from src.llm.json_parser import parse_json_object
from src.policy.retriever import PolicyRetriever
from src.policy_reasoner import propose_policy_decision
from src.schemas import RequestContext, RequesterContext, TrustTier
from src.tools.mock_data import get_employee_by_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Policy Agent CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    retrieve_parser = subparsers.add_parser("retrieve", help="Retrieve policy sections")
    retrieve_parser.add_argument("query", help="Policy retrieval query")
    retrieve_parser.add_argument("--top-k", type=int, default=8)
    retrieve_parser.add_argument("--no-graph", action="store_true", help="Disable graph expansion")

    llm_test_parser = subparsers.add_parser("llm-test", help="Call Ollama in JSON mode")
    llm_test_parser.add_argument("prompt", help="Prompt to send to the local LLM")

    llm_raw_parser = subparsers.add_parser("llm-raw", help="Call Ollama and print raw text")
    llm_raw_parser.add_argument("prompt", help="Prompt to send to the local LLM")

    intent_parser = subparsers.add_parser("intent", help="Extract structured intent from a request")
    intent_parser.add_argument("message", help="User request to structure")
    intent_parser.add_argument("--trust", choices=[tier.value for tier in TrustTier], required=True)
    intent_parser.add_argument("--requester", required=True, help="Requester employee ID")

    reason_parser = subparsers.add_parser("reason", help="Extract intent, retrieve policy, and propose a decision")
    reason_parser.add_argument("message", help="User request to reason about")
    reason_parser.add_argument("--trust", choices=[tier.value for tier in TrustTier], required=True)
    reason_parser.add_argument("--requester", required=True, help="Requester employee ID")
    reason_parser.add_argument("--top-k", type=int, default=8)

    args = parser.parse_args()

    if args.command == "retrieve":
        _retrieve(args.query, args.top_k, use_graph_expansion=not args.no_graph)
    elif args.command == "llm-test":
        _llm_test(args.prompt)
    elif args.command == "llm-raw":
        _llm_raw(args.prompt)
    elif args.command == "intent":
        _intent(args.message, args.trust, args.requester)
    elif args.command == "reason":
        _reason(args.message, args.trust, args.requester, args.top_k)


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


def _llm_test(prompt: str) -> None:
    client = get_default_llm_client()
    response = client.generate(prompt, temperature=0.0, format_json=True)
    parsed = parse_json_object(response)
    _print_json(parsed)


def _llm_raw(prompt: str) -> None:
    client = get_default_llm_client()
    response = client.generate(prompt, temperature=0.0)
    print(response)


def _print_json(data: dict) -> None:
    try:
        from rich.console import Console

        Console().print_json(json.dumps(data, indent=2))
    except ImportError:
        print(json.dumps(data, indent=2))


def _intent(message: str, trust_tier: str, requester_id: str) -> None:
    request = _build_request_context(message, trust_tier, requester_id)
    intent = extract_intent(request)
    _print_json(intent.model_dump(mode="json"))


def _reason(message: str, trust_tier: str, requester_id: str, top_k: int) -> None:
    request = _build_request_context(message, trust_tier, requester_id)
    intent = extract_intent(request)
    retrieved_sections = PolicyRetriever().retrieve(message, top_k=top_k)
    proposal = propose_policy_decision(request, intent, retrieved_sections)

    print("Extracted intent:")
    _print_json(intent.model_dump(mode="json"))
    print("\nRetrieved policy sections:")
    for section in retrieved_sections:
        print(f"- {section['section_id']} {section['title']}")
    print("\nPolicy proposal:")
    _print_json(proposal.model_dump(mode="json"))


def _build_request_context(message: str, trust_tier: str, requester_id: str) -> RequestContext:
    return RequestContext(
        request_id=f"REQ-{uuid4().hex[:8]}",
        conversation_id=f"CONV-{uuid4().hex[:8]}",
        trust_tier=TrustTier(trust_tier),
        requester=_build_requester_context(requester_id),
        message=message,
    )


def _build_requester_context(employee_id: str) -> RequesterContext:
    employee = get_employee_by_id(employee_id)
    if employee is None:
        return RequesterContext(
            employee_id=employee_id,
            name="Unknown Requester",
            department="Unknown",
            team="Unknown",
            role="Unknown",
            is_manager=False,
            verified=False,
            reports=[],
        )

    return RequesterContext(
        employee_id=employee.employee_id,
        name=employee.name,
        department=employee.department,
        team=employee.team,
        role=employee.title,
        is_manager=bool(employee.employee_id in {"EMP-2011", "EMP-1500", "EMP-2200", "EMP-1060"}),
        verified=True,
        reports=[],
    )


if __name__ == "__main__":
    main()
