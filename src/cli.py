# -----------------------------------------------------------------------------
# CLI overview
# -----------------------------------------------------------------------------
# ask                 Full end-to-end agent; use --debug for internals.
# retrieve            Policy retrieval only.
# intent              Intent extraction only.
# reason              Intent + retrieval + LLM proposal; no final enforcement.
# guard               Adds deterministic policy guard; no tool execution.
# execute             Runs guarded tool execution with sanitized output.
# llm-test            Tests local Ollama JSON generation.
# llm-raw             Tests local Ollama raw text generation.
# logs                Reads recent decision logs.
# eval                Runs scenario evaluation.
# generate-scenarios  Generates additional evaluation scenarios.
# chat                Simple interactive CLI loop.
#
# Helper functions:
# _build_request_context    Builds RequestContext from CLI args.
# _build_requester_context  Resolves requester metadata from mock data.
# _print_json               Pretty-prints JSON output.
# _preview                  Shortens long text for terminal display.
# -----------------------------------------------------------------------------

from __future__ import annotations

import argparse
import json
import logging
import os
import warnings
from uuid import uuid4

os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")
# Keep local CLI demos clean while preserving real exceptions and other warnings.
warnings.filterwarnings("ignore", message=".*unauthenticated requests to the HF Hub.*")


class _HfHubAuthWarningFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "unauthenticated requests to the HF Hub" not in record.getMessage()


_hf_auth_filter = _HfHubAuthWarningFilter()
logging.getLogger("huggingface_hub").addFilter(_hf_auth_filter)
logging.getLogger("huggingface_hub.utils._auth").addFilter(_hf_auth_filter)
# The HF Hub unauthenticated-token advisory is logged from its auth helper.
# Suppress only that warning in normal CLI demos; model loading errors still surface.
logging.getLogger("huggingface_hub.utils._auth").setLevel(logging.ERROR)

from src.agent import PolicyAgent
from eval.generate_scenarios import generate_scenarios
from eval.run_eval import run_eval
from src.intent import extract_intent
from src.llm.client import get_default_llm_client
from src.llm.json_parser import parse_json_object
from src.logging.decision_logger import DecisionLogger
from src.policy.policy_guard import enforce_policy
from src.policy.retriever import PolicyRetriever, load_policy_cards
from src.policy_reasoner import propose_policy_decision
from src.schemas import RequestContext, RequesterContext, TrustTier
from src.tools.safe_tool_executor import execute_final_decision
from src.tools.mock_data import get_employee_by_id, is_manager


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

    guard_parser = subparsers.add_parser("guard", help="Run intent, retrieval, proposal, and policy guard")
    guard_parser.add_argument("message", help="User request to evaluate")
    guard_parser.add_argument("--trust", choices=[tier.value for tier in TrustTier], required=True)
    guard_parser.add_argument("--requester", required=True, help="Requester employee ID")
    guard_parser.add_argument("--top-k", type=int, default=8)

    execute_parser = subparsers.add_parser("execute", help="Run the guarded pipeline and safely execute approved tools")
    execute_parser.add_argument("message", help="User request to evaluate and execute if allowed")
    execute_parser.add_argument("--trust", choices=[tier.value for tier in TrustTier], required=True)
    execute_parser.add_argument("--requester", required=True, help="Requester employee ID")
    execute_parser.add_argument("--top-k", type=int, default=8)
    execute_parser.add_argument("--show-raw", action="store_true", help="Print raw tool output for internal debugging")

    ask_parser = subparsers.add_parser("ask", help="Run the full agent and print the final response")
    ask_parser.add_argument("message", help="User request")
    ask_parser.add_argument("--trust", choices=[tier.value for tier in TrustTier], required=True)
    ask_parser.add_argument("--requester", required=True, help="Requester employee ID")
    ask_parser.add_argument("--debug", action="store_true", help="Print intermediate pipeline artifacts")
    ask_parser.add_argument("--no-log", action="store_true", help="Disable decision logging for this request")

    logs_parser = subparsers.add_parser("logs", help="Inspect recent decision logs")
    logs_parser.add_argument("--last", type=int, default=5, help="Number of recent log records to show")
    logs_parser.add_argument("--json", action="store_true", help="Print raw JSON records")

    eval_parser = subparsers.add_parser("eval", help="Run evaluation scenarios")
    eval_parser.add_argument("--input", default="eval/provided_scenarios.jsonl")
    eval_parser.add_argument("--output", default="eval/results/provided_results.jsonl")

    generate_parser = subparsers.add_parser("generate-scenarios", help="Generate additional evaluation scenarios")
    generate_parser.add_argument("--n", type=int, default=30)
    generate_parser.add_argument("--output", default="eval/generated_scenarios.jsonl")

    subparsers.add_parser("chat", help="Start a simple interactive chat loop")

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
    elif args.command == "guard":
        _guard(args.message, args.trust, args.requester, args.top_k)
    elif args.command == "execute":
        _execute(args.message, args.trust, args.requester, args.top_k, args.show_raw)
    elif args.command == "ask":
        _ask(args.message, args.trust, args.requester, args.debug, no_log=args.no_log)
    elif args.command == "logs":
        _logs(args.last, args.json)
    elif args.command == "eval":
        _eval(args.input, args.output)
    elif args.command == "generate-scenarios":
        _generate_scenarios(args.n, args.output)
    elif args.command == "chat":
        _chat()


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


def _guard(message: str, trust_tier: str, requester_id: str, top_k: int) -> None:
    request = _build_request_context(message, trust_tier, requester_id)
    intent = extract_intent(request)
    retrieved_sections = PolicyRetriever().retrieve(message, top_k=top_k)
    proposal = propose_policy_decision(request, intent, retrieved_sections)
    final_decision = enforce_policy(request, intent, proposal, policy_cards=load_policy_cards())

    print("Extracted intent:")
    _print_json(intent.model_dump(mode="json"))
    print("\nPolicy proposal:")
    _print_json(proposal.model_dump(mode="json"))
    print("\nFinal decision:")
    _print_json(final_decision.model_dump(mode="json"))


def _execute(message: str, trust_tier: str, requester_id: str, top_k: int, show_raw: bool) -> None:
    request = _build_request_context(message, trust_tier, requester_id)
    intent = extract_intent(request)
    retrieved_sections = PolicyRetriever().retrieve(message, top_k=top_k)
    proposal = propose_policy_decision(request, intent, retrieved_sections)
    final_decision = enforce_policy(request, intent, proposal, policy_cards=load_policy_cards())
    tool_call = execute_final_decision(final_decision)

    print("Final decision:")
    _print_json(final_decision.model_dump(mode="json"))
    print("\nTool call record:")
    public_record = tool_call.model_dump(mode="json")
    if not show_raw:
        public_record.pop("raw_tool_result", None)
    _print_json(public_record)
    print("\nSafe result:")
    _print_json(tool_call.safe_tool_result or {})
    print("\nFields released:")
    _print_json({"fields_released": tool_call.fields_released})
    print("\nFields blocked:")
    _print_json({"fields_blocked_by_policy": tool_call.fields_blocked_by_policy})
    print("\nFields not requested:")
    _print_json({"fields_not_requested": tool_call.fields_not_requested})
    if show_raw:
        print("\nDEBUG RAW TOOL RESULT - INTERNAL ONLY")
        _print_json(tool_call.raw_tool_result or {})


def _ask(message: str, trust_tier: str, requester_id: str, debug: bool, no_log: bool) -> None:
    request = _build_request_context(message, trust_tier, requester_id)
    result = PolicyAgent(enable_logging=not no_log).handle_request(request)
    if not debug:
        print(result["response_text"])
        return

    print("Intent:")
    _print_json(result["intent"].model_dump(mode="json"))
    print("\nRetrieved policy sections:")
    for section in result["retrieved_policy_sections"]:
        print(f"- {section['section_id']} {section['title']}")
    print("\nPolicy proposal:")
    _print_json(result["policy_proposal"].model_dump(mode="json"))
    print("\nFinal decision:")
    _print_json(result["final_decision"].model_dump(mode="json"))
    print("\nTool call record:")
    debug_tool_record = result["tool_call_record"].model_dump(mode="json")
    debug_tool_record.pop("raw_tool_result", None)
    _print_json(debug_tool_record)
    print("\nDecision log:")
    if result.get("decision_log_written"):
        print(f"Decision log written: {result['decision_log_path']}")
    elif result.get("logging_warning"):
        print(f"Warning: {result['logging_warning']}")
    else:
        print("Decision logging disabled.")
    print("\nFinal response:")
    print(result["response_text"])


def _logs(last: int, print_json: bool) -> None:
    logger = DecisionLogger()
    records = logger.read_last(last)
    if print_json:
        _print_json(records)
        return

    if not records:
        print("No decision logs found.")
        return

    for record in records:
        final_decision = record.get("final_decision", {})
        tool_call = record.get("tool_call", {})
        requester = f"{record.get('requester_id')}"
        if record.get("requester_name"):
            requester += f" / {record.get('requester_name')}"

        print(f"{record.get('timestamp')}")
        print(f"request_id: {record.get('request_id')}")
        print(f"trust tier: {record.get('trust_tier')}")
        print(f"requester: {requester}")
        print(f"user message: {record.get('user_message')}")
        print(f"final_action: {final_decision.get('final_action')}")
        print(f"final_tool: {final_decision.get('final_tool')}")
        print(f"called tool: {tool_call.get('called')}")
        print(f"policy citations: {', '.join(final_decision.get('policy_citations', []))}")
        print(f"fields_released: {', '.join(tool_call.get('fields_released', []))}")
        print(f"fields_blocked_by_policy: {', '.join(tool_call.get('fields_blocked_by_policy', []))}")
        print(f"final response preview: {_preview(record.get('final_response', ''), max_length=220)}")
        print("")


def _eval(input_path: str, output_path: str) -> None:
    summary = run_eval(input_path, output_path)
    print(f"Evaluated {summary['total']} scenarios")
    print(f"Passed: {summary['overall_pass_count']}/{summary['total']}")
    print(f"Results: {summary['results_path']}")
    print(f"Summary: {summary['summary_path']}")


def _generate_scenarios(n: int, output_path: str) -> None:
    result = generate_scenarios(n=n, output_path=output_path)
    print(f"Generated {result['count']} scenarios")
    print(f"Output: {result['output_path']}")
    print(f"Fallback used: {result['fallback_used']}")


def _chat() -> None:
    trust_tier = input("Trust tier (blue/red/grey): ").strip().lower()
    requester_id = input("Requester employee ID: ").strip()
    agent = PolicyAgent()

    while True:
        message = input("> ").strip()
        if message.lower() in {"exit", "quit"}:
            break
        request = _build_request_context(message, trust_tier, requester_id)
        result = agent.handle_request(request)
        print(result["response_text"])


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
        is_manager=is_manager(employee.employee_id),
        verified=True,
        reports=[],
    )


if __name__ == "__main__":
    main()
