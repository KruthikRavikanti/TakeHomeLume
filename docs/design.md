# Design Notes

Policy Agent keeps the exact assignment seed in `policy/gaggia_seed_policy.md` and uses the expanded, example-free runtime policy in `policy/gaggia_it_helpdesk_policy.md` for retrieval.

Retrieval is graph-aware hybrid retrieval: semantic embeddings plus BM25 find relevant policy sections, then the section graph adds parent and referenced context. Retrieval returns evidence only; the deterministic policy guard will enforce policy decisions later using `policy/policy_cards.jsonl` and verified requester context.
