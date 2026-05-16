# Policy Expansion Notes

The original seed policy is stored exactly in `policy/gaggia_seed_policy.md`.

The expanded policy is stored in `policy/gaggia_it_helpdesk_policy.md`.

The expanded policy is the document used by the retriever at runtime.

The seed policy is retained for traceability.

The expansion adds realistic corporate IT policy detail but does not override or weaken any seed rule.

The most important safety additions are trust-tier handling, policy conflict resolution, data classification, privileged access, legal hold, and audit logging.

The expanded runtime policy intentionally avoids scenario examples; evaluation scenarios belong under `eval/`.

The retriever uses BM25, semantic embeddings, and graph expansion to return policy evidence only. Deterministic enforcement will happen later in the policy guard.
