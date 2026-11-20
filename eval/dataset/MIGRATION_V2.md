# Migrating the evaluation set to wiki v2

Written on 2026-11-20, **before** running the re-assessment it describes.

The wiki was rewritten at Area-Reborn `b2cdaa9` (72 articles audited against the game's
code, about 400 corrections, a new `faq` article, 17 new sections elsewhere, 2 sections
removed: `notifications#discord` and `alliance_basics#discord`). Candidates and reference
answers were drafted from the previous snapshot (`ef59d47`), so many answers are now wrong,
some unanswerable questions now have an answer, and positional section keys (`slug#N`) moved
where sections were inserted.

## What is kept

- **Version 1 is archived as it was** in `eval/dataset/v1/` (candidates, reviews, questions,
  stats). The phase 2 benchmark figures in `eval/results/` were computed on it and stay
  valid for the wiki snapshot `ef59d47`; they are not mixed with v2 figures.
- **Question ids, questions and splits do not change.** A question keeps its split even if
  its kind or answer changes: the split was frozen before any review and stays so.
- **Review decisions are carried over when the question is still valid** (rules below).

## Steps

1. **Section map, deterministic.** Each old section `(slug, index)` is mapped to its new
   position through its French anchor, which the rewrite kept for every existing section
   (`work/v2/section_map.json`). A reference to a removed section is dropped and flagged.
2. **Re-assessment, by LLM, against the new wiki.** For every candidate, sections are pooled
   again from the five retrieval strategies over the v2 index (top 10 each) plus the
   remapped sources, and `deepseek-v4-pro` (thinking disabled, temperature 0) returns:
   which sections answer the question; whether they answer it fully; whether the question
   still makes sense in the current game; whether the old reference answer is *consistent*,
   *contradicted* or *incomplete* compared with these sections (any differing number, time,
   name or condition counts as contradicted); game terms that were renamed; a new reference
   answer in the question's language with a French gloss; the best kind for the question now.
   Output: `work/v2/reassessments.jsonl`.
3. **Status of each candidate, by code** (`sextant.eval.migration.decide_status`):

   | Previous state | Condition on the re-assessment | v2 status |
   |---|---|---|
   | kept or corrected | question valid, same answerable/unanswerable nature, old answer *consistent*, no renamed term, no removed source | **carried**: the reviewed answer is kept, relevance updated, no new review needed |
   | kept or corrected | anything else | **revalidate**, with the reasons, the old answer and the proposed new one |
   | rejected as a wrong answer | — | **revalidate** (the answer was regenerated) |
   | rejected for another reason | — | stays **rejected** |
   | not reviewed yet | — | **to review**, with the regenerated answer and relevance |

   A former unanswerable question that the wiki now answers changes kind (proposed by the
   re-assessment) and is always revalidated. Between answerable kinds (factual, procedural…)
   the original kind is kept: the label does not change what is measured.
4. **New unanswerable questions.** If fewer than the plan's ~15 % unanswerable questions
   remain, new ones are drafted against the v2 wiki (the FAQ included), verified by the same
   pooling and judge (no section may answer them), written in the six languages with the
   phase 1 quotas, and given new ids after q288. Their split is frozen when they are created:
   the existing split of their article, or the usual balancing for out-of-scope questions.
5. **Review.** The review page shows *revalidate* and *to review* items; a decision is
   stored with the wiki revision it was taken on, so a decision taken on v1 never validates
   a v2 answer that changed.
6. **Benchmarks.** Phase 2 is run again on v2 once the review is done: decisions on dev by
   the coded rules, one run on test, both recorded as v2 in `eval/results/`.
