# Retrieval benchmark — split `dev`

66 monolingual answerable questions (71 answerable, 84 in total), top 10 sections per query. Source: `eval/results/retrieval_dev_3_rerank.json`.

| Strategy | MRR | nDCG@10 | Recall@5 | Hit@1 | Hit@5 | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|
| `rerank:bge-m3:dense:e5-large` | 0.967 | 0.909 | 0.872 | 0.939 | 1.000 | 9483.5 | 14363.8 |
| `rerank:bge-m3@10:dense:e5-large` | 0.962 | 0.871 | 0.855 | 0.939 | 0.985 | 2018.7 | 4097.1 |

## Cross-lingual questions (reported apart, not used for decisions)

| Strategy | n | MRR | nDCG@10 | Recall@5 | Hit@1 |
|---|---|---|---|---|---|
| `rerank:bge-m3:dense:e5-large` | 5 | 0.900 | 0.924 | 0.853 | 0.800 |
| `rerank:bge-m3@10:dense:e5-large` | 5 | 0.900 | 0.904 | 0.843 | 0.800 |
