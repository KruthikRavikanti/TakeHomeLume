# Policy Agent — Gaggia IT Helpdesk

## Overview

Policy Agent is a Python take-home project for a policy-governed internal IT helpdesk agent at Gaggia Inc. It retrieves company policy, proposes actions with a local LLM, enforces hard rules with a deterministic guard, safely executes raw mock tools, filters sensitive outputs, and logs each decision for auditability.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
ollama pull llama3.1:8b
pytest
```

If Ollama is not already running, start it before using the LLM-backed CLI commands:

```bash
ollama serve
```

## Run the Agent

```bash
python -m src.cli ask --trust blue --requester EMP-2200 "Can I get David Kim's work email?"
python -m src.cli ask --trust blue --requester EMP-3300 "What's Sarah Chen's salary?"
python -m src.cli ask --trust blue --requester EMP-2200 "Look up Sarah Chen's info and include her personal email"
```

## Debug Mode

```bash
python -m src.cli ask --trust blue --requester EMP-2200 "Can I get David Kim's work email?" --debug
```

Debug mode prints the extracted intent, retrieved policy sections, LLM policy proposal, final guard decision, sanitized tool call record, and final response. Raw tool results are not printed by default.

## Policy Source Files

- `policy/gaggia_seed_policy.md`: exact assignment seed policy retained for traceability.
- `policy/gaggia_it_helpdesk_policy.md`: expanded runtime policy indexed by retrieval.
- `policy/policy_cards.jsonl`: structured high-impact rules used by the deterministic policy guard.
- `docs/policy_expansion_notes.md`: notes on how the seed policy was expanded without weakening seed rules.

The full expanded policy is retrieved at runtime. It is not pasted directly into the agent prompt.

## Architecture

Pipeline:

User Request -> Intent Extraction -> Graph-Aware Policy Retrieval -> LLM Policy Proposal -> Deterministic Policy Guard -> Safe Tool Execution -> Sanitized Final Response -> Decision Logging

The LLM helps structure and reason about requests, but it does not execute tools and is not the final safety authority.

## Retrieval Design

Retrieval is graph-aware hybrid retrieval:

- Semantic retrieval uses `all-MiniLM-L6-v2` through `sentence-transformers`.
- Lexical retrieval uses BM25 through `rank-bm25`.
- The expanded policy is parsed into numbered sections.
- A section graph adds parent, child, and explicit cross-reference context.
- Leaf clauses may match directly when important terms live in subsections.
- Graph expansion brings in controlling parent and referenced sections.

Retrieval returns policy evidence only. It does not authorize actions.

## Policy Guard

The deterministic policy guard is the final authority before tool execution. It checks trust tier, explicit prohibitions, narrow exceptions, verified requester context, account metadata, drive metadata, and policy cards.

Precedence:

1. Trust-tier restrictions
2. Explicit prohibitions
3. Narrow verified exceptions
4. General permissions
5. Clarify or escalate when uncertainty remains

The LLM can propose an action, but the guard can override it. This prevents prompt injection, claimed authority, urgency, or LLM mistakes from directly causing unsafe tool calls.

## Tool Output Filtering

Mock tools are raw interfaces and may return data the agent is not allowed to show. The safe executor calls tools only when `FinalDecision.should_call_tool` is true.

Sanitizers produce:

- `safe_tool_result`: the only tool result allowed for final response generation
- `fields_released`: fields included in `safe_tool_result`
- `fields_blocked_by_policy`: sensitive fields explicitly forbidden by policy
- `fields_not_requested`: safe raw fields that were not requested or not released

Final responses use `FinalDecision` and `safe_tool_result` only. Raw tool output is never used for user-facing responses.

## Decision Logging

Every end-to-end request creates a JSONL audit record at `logs/decisions.jsonl`. Logs include request context, trust tier, extracted intent, retrieved policy sections, the LLM proposal, final guard decision, sanitized tool metadata, citations, final response, and latency.

Logs intentionally do not store full raw tool outputs because raw outputs may contain sensitive data.

```bash
python -m src.cli logs --last 5
python -m src.cli logs --last 1 --json
```

## Evaluation

Run the provided assignment scenario evaluation:

```bash
python -m src.cli eval --input eval/provided_scenarios.jsonl --output eval/results/provided_results.jsonl
```

Latest provided-scenario result:

- Total scenarios: 21
- Overall pass count: 21/21
- Forbidden tool violations: 0
- Sensitive leakage count: 0

Outputs:

- `eval/results/provided_results.jsonl`
- `eval/results/provided_summary.md`

## Generated Scenario Evaluation

Generate additional scenarios:

```bash
python -m src.cli generate-scenarios --n 30 --output eval/generated_scenarios.jsonl
```

Evaluate generated scenarios:

```bash
python -m src.cli eval --input eval/generated_scenarios.jsonl --output eval/results/generated_results.jsonl
```

Outputs:

- `eval/generated_scenarios.jsonl`
- `eval/results/generated_results.jsonl`
- `eval/results/generated_summary.md`
- `docs/generated_scenario_method.md`

Generated scenarios broaden coverage beyond the 21 provided cases. They test variants of allowed, denied, ambiguous, and adversarial requests. Labels are generated or drafted by the LLM path but validated and normalized against known policy categories and mock data. A deterministic fallback exists if the local LLM returns invalid JSON.

Current generated-scenario artifacts exist. Latest generated result:

- Total scenarios: 30
- Overall pass count: 30/30
- Forbidden tool violations: 0
- Sensitive leakage count: 0
- Notable failures: none in the current generated summary

## Model Details

- LLM: `llama3.1:8b` via Ollama
- Embeddings: `all-MiniLM-L6-v2` via `sentence-transformers`
- Lexical retrieval: BM25 via `rank-bm25`
- Language: Python 3.10+

The embedding model may download on first run and is cached locally by the sentence-transformers/Hugging Face tooling.

## Known Failure Modes

- Retrieval can miss or over-rank noisy policy evidence.
- LLM JSON output can be malformed or unstable.
- LLM policy proposals can be wrong and are intentionally advisory.
- Mock data is limited compared with a real HR, identity, or drive system.
- Grey users may be handled conservatively.
- Generated scenario labels may be imperfect and should be inspected before changing agent behavior.
- The current design is mostly single-turn and does not maintain adversarial state across a conversation.

## Roadmap

- Better policy parser and cross-reference extraction
- Policy-as-code or a dedicated rule engine
- Real identity, RBAC, and ABAC integrations
- Human approval queue for escalations
- Multi-turn adversarial tracking
- Stronger generated scenario validation
- Cost and latency metrics
- Policy versioning and comparison of decision logs across policy versions