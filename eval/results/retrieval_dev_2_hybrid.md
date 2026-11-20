# Retrieval benchmark — split `dev`

66 monolingual answerable questions (71 answerable, 84 in total), top 10 sections per query. Source: `eval/results/retrieval_dev_2_hybrid.json`.

| Strategy | MRR | nDCG@10 | Recall@5 | Hit@1 | Hit@5 | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|
| `hybrid:e5-large` | 0.906 | 0.834 | 0.804 | 0.849 | 1.000 | 91.1 | 137.3 |

## Cross-lingual questions (reported apart, not used for decisions)

| Strategy | n | MRR | nDCG@10 | Recall@5 | Hit@1 |
|---|---|---|---|---|---|
| `hybrid:e5-large` | 5 | 0.700 | 0.626 | 0.617 | 0.600 |
