# Generated Scenario Method

## Goal

Generated scenarios broaden regression coverage beyond the 21 provided assignment cases. They exercise additional variants of allowed, denied, ambiguous, and adversarial IT helpdesk requests.

## Model

The generator attempts to use the local project LLM, `llama3.1:8b` via Ollama, to draft scenarios as strict JSON.

## Prompt Approach

The prompt asks for a JSON array only and constrains drafts to known mock employees, accounts, and drives. It requests coverage across directory lookup, personal contact restrictions, HR data restrictions, general HR policy, password resets, shared drive access, restricted/legal-hold/personal drives, Team Red adversarial requests, Team Grey ambiguity, mixed allowed/blocked lookups, manager active-status exceptions, non-manager active-status denials, and claimed-authority cases.

## Validation and Normalization

Generated labels are treated as draft labels, not perfect ground truth. The generator normalizes each scenario and validates:

- trust tier
- expected action
- expected tool
- requester ID
- required list fields
- sensitive-field leak checks
- Team Red tool expectations
- duplicate messages from the provided scenario set

Invalid scenarios are discarded or corrected only when the fix is obvious.

## Deterministic Fallback

A deterministic fallback list exists if the local LLM returns invalid JSON, too few usable scenarios, or cannot be reached. The fallback scenarios use the same schema and are still normalized and validated before writing `eval/generated_scenarios.jsonl`.

## Limitations

Generated scenarios may be biased by the prompt. Generated labels are useful for regression coverage, but they are not a formal oracle and do not prove correctness. Failures should be inspected before changing agent behavior because a generated label may be wrong or ambiguous.
