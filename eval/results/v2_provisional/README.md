# Provisional retrieval measure on wiki v2 (dev only)

Run on 2026-11-20 on the production wiki (`df6465b`, index rebuilt from scratch), **while the
review of the v2 evaluation set is under way**. It is an early signal, not the phase 2
benchmark on v2: no decision rule is applied, and **the test split is not touched**, so the
one test run the protocol allows stays for after the review.

Two item sets, both from the dev split, built by `python -m sextant.eval.review provisional`:

| Set | What it is | Dev items | Limits |
|---|---|---|---|
| [`validated.jsonl`](validated.jsonl) | items a human validated on v2 (carried answers and decisions taken on v2) | 31 (29 monolingual answerable) | small; mostly carried answers, the questions the rewrite changed least |
| [`proposed.jsonl`](proposed.jsonl) | every live candidate with its **proposed, unreviewed** relevance | 163 (135 monolingual answerable) | labels from the LLM judge over sections pooled from these very strategies (pooling bias) |

Strategies and metrics as in phase 2 (`eval/PROTOCOL.md`), top 10 sections, monolingual
answerable questions; cross-lingual ones are reported apart in each file.

| Strategy | nDCG@10 validated | nDCG@10 proposed | Recall@5 proposed | Hit@1 proposed | p50 ms |
|---|---|---|---|---|---|
| `bm25` | 0.642 | 0.636 | 0.683 | 0.496 | 1.4 |
| `dense:e5-large` (the retained strategy) | **0.815** | **0.791** | **0.803** | 0.748 | 90 |
| `hybrid:e5-large` | 0.788 | 0.796 | 0.791 | 0.726 | 91 |

For reference, on wiki v1 (`ef59d47`), dev split, 66 questions: `dense:e5-large` 0.823 and
`bm25` 0.758 nDCG@10 ([`../retrieval_dev_1_first_stage.md`](../retrieval_dev_1_first_stage.md)).
Different questions and labels, so the comparison is indicative only.

Sources: [`retrieval_dev_validated.md`](retrieval_dev_validated.md),
[`retrieval_dev_proposed.md`](retrieval_dev_proposed.md) and their JSON.
