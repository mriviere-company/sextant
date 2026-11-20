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

Two problems found in the wiki itself, to fix in Area-Reborn: the glossary says a lower
DEFCON is more tense while `diplomacy#defcon` says 5 is the maximum alert; the English
`invasion` article names its new section `cancel` instead of the French anchor `annuler`.
