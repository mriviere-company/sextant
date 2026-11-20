# Index freshness after the wiki rewrite (2026-11-20)

Checked offline, without an LLM, after `make index` on wiki `b2cdaa9`:

- The `chunks` table equals `corpus/processed/chunks.jsonl`: same 2 562 ids, same embedded
  text (SHA-256 compared chunk by chunk); the three embedding tables hold 2 562 rows each.
- None of these outdated wordings remains in the French chunks: "Moon Maker" as a name
  (it survives only as an alias of the Lunar), a Discord alert for incoming enemy fleets,
  fuel paid in water, a +250 PDG quest bonus.
- For each of the 18 probes of `eval/probes/wiki_v2_facts.jsonl`, the top 5 chunks of
  `dense:e5-large` (the served configuration) contain the corrected fact: 18 / 18.

The second half of the check, the served answers judged against the wiki
(`python -m sextant.eval.consistency`), could not run: the DeepSeek account returned
402 Insufficient Balance.

Two problems found in the wiki itself. The glossary said a lower DEFCON is more tense while
`diplomacy#defcon` says 5 is the maximum alert: the glossary was wrong (the game sets 0 by
default and 5 on a declaration of war) and was fixed in the six languages at Area-Reborn
`f142383`. The English `invasion` article still names its new section `cancel` instead of
the French anchor `annuler`.

**Update for `f142383` (glossary only).** The corpus was refreshed: 8 chunks changed and 1
was added (`ru:glossary#az:2`), all in the glossary, none removed. The incremental reindex
re-embedded those 9 chunks in the three models (2 minutes instead of about 50 for the
whole corpus); the index again equals the corpus chunk by chunk (2 563 chunks).
