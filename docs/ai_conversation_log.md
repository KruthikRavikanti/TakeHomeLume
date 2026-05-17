# AI Conversation Log

## Summary

AI tools were used as implementation assistants for architecture planning, Codex prompts, debugging, tests, and documentation. The project was built incrementally and validated with unit tests, manual CLI checks, and scenario evaluation.

## Major Prompt Categories

- Initial architecture design
- Step-by-step build prompts
- Policy expansion
- Retrieval design
- Ollama client
- Intent extraction
- Policy reasoner
- Deterministic guard
- Safe tool execution
- Agent orchestration
- Decision logging
- Evaluation
- Documentation polish

## How Outputs Were Evaluated

Outputs were evaluated with unit tests, manual CLI runs, provided-scenario evaluation, generated-scenario evaluation, sensitive-data leakage checks, and inspection of cases where the deterministic guard overrides unsafe or incorrect LLM proposals.

## Examples of Iteration

- Removed examples from the runtime policy because they polluted retrieval.
- Switched to graph-aware hybrid retrieval so parent, child, and referenced sections stay connected.
- Fixed mock data to align with provided scenarios, including standard account reset and manager reporting-chain cases.
- Split field accounting into `fields_released`, `fields_blocked_by_policy`, and `fields_not_requested`.
- Added decision logs without storing raw sensitive tool values.

## Responsibility Statement

AI tools were used as implementation assistants, but final architecture decisions, safety boundaries, and evaluation criteria were reviewed and validated through tests and manual inspection.
