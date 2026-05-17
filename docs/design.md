# Design

## Overview

Policy Agent is a policy-governed internal IT helpdesk agent for Gaggia Inc. It handles common employee support requests by retrieving relevant policy evidence, proposing an action with a local LLM, enforcing hard policy rules deterministically, safely executing mock tools, and returning sanitized user-facing responses.

## Architecture

Pipeline:

User Request -> Intent Extraction -> Graph-Aware Policy Retrieval -> LLM Policy Proposal -> Deterministic Policy Guard -> Safe Tool Execution -> Sanitized Final Response -> Decision Logging

- Intent Extraction: converts the user message into structured intent, target entities, requested fields, claims, and rough risk.
- Graph-Aware Policy Retrieval: retrieves relevant numbered policy sections and expands them through parent, child, and cross-reference relationships.
- LLM Policy Proposal: uses retrieved evidence to propose an action, tool, citations, and explanation.
- Deterministic Policy Guard: makes the final pre-tool decision using policy cards, trust tier, verified context, and mock metadata.
- Safe Tool Execution: calls raw mock tools only when approved by the guard.
- Sanitized Final Response: uses only `safe_tool_result`, never raw tool output.
- Decision Logging: writes an inspectable JSONL audit trail for each end-to-end request.

## Policy Source Files

- `policy/gaggia_seed_policy.md`: exact seed policy retained for traceability.
- `policy/gaggia_it_helpdesk_policy.md`: expanded runtime policy indexed by retrieval.
- `policy/policy_cards.jsonl`: structured high-impact rules used by the deterministic policy guard.

The expanded runtime policy is not pasted wholesale into prompts. The agent retrieves relevant sections at decision time.

## Retrieval Design

Retrieval combines semantic embeddings with BM25 lexical retrieval. Embeddings help with paraphrases, while BM25 preserves exact security terms such as `salary`, `Team Red`, `legal-hold`, and `service account`.

The policy is parsed into numbered sections and represented as a graph. Parent/child edges come from section numbering, and reference edges come from explicit cross-references such as "Section 4.2". Leaf clauses may match directly because important policy language often lives in subsections. Graph expansion then brings in controlling parent sections and referenced context.

Retrieval provides evidence only. It does not authorize actions, deny requests, call tools, or enforce safety.

## LLM Usage

The project uses `llama3.1:8b` through Ollama. The LLM is used for:

- intent extraction
- policy decision proposals
- generated scenario drafting

The LLM does not directly execute tools. Its policy proposal is advisory and can be overridden by the deterministic guard.

## Deterministic Policy Guard

The deterministic policy guard is the final authority before tool execution. It enforces trust-tier restrictions, explicit prohibitions, narrow exceptions, verified requester context, employee/account metadata, and drive metadata.

Precedence:

1. Trust-tier restrictions
2. Explicit prohibitions
3. Narrow verified exceptions
4. General permissions
5. Clarify or escalate when uncertainty remains

This prevents prompt injection, claimed authority, urgency, or LLM mistakes from directly causing unsafe tool calls.

## Tool Execution and Sanitization

Mock tools are intentionally raw and may return unsafe fields. For example, `lookup_employee` can return personal contact data, salary, performance rating, and employment status.

The safe executor calls tools only when `FinalDecision.should_call_tool` is true. Sanitizers separate raw fields into:

- `fields_released`: fields included in `safe_tool_result`
- `fields_blocked_by_policy`: sensitive fields explicitly forbidden by policy
- `fields_not_requested`: safe raw fields that were not requested or not released

Final responses only use `safe_tool_result` plus the final guard decision. Raw tool results are never used for user-facing responses.

## Decision Logging

Decision logs include request context, trust tier, extracted intent, retrieved policy sections, LLM proposal, final guard decision, sanitized tool metadata, citations, final response, and latency.

Logs do not store full raw tool outputs because raw outputs may contain sensitive data. They store raw field names and sanitized metadata only.

## Known Failure Modes

- Retrieval misses or noisy retrieval can provide incomplete evidence.
- LLM JSON output may be malformed or unstable.
- LLM policy proposals can be wrong and must remain advisory.
- Mock data is limited and does not represent a full identity or HR system.
- Grey users may be handled conservatively, which can create extra clarifications or escalations.
- Generated scenario labels may be imperfect because they are draft labels, not a formal oracle.
- The current agent is mostly single-turn and does not maintain adversarial state across a conversation.

## Roadmap

- Better policy parser with stronger markdown and cross-reference handling
- Policy-as-code or a dedicated rule engine for guard logic
- Real identity, RBAC, and ABAC integration
- Human approval queue for escalations
- Multi-turn adversarial tracking
- Better generated scenario validation
- Cost and latency metrics
- Policy versioning and audit comparisons across versions
