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

   **Amendment, before the statuses were used (2026-11-20).** A manual check of q002 found
   the re-assessment had called an outdated answer *consistent* (right figure, wrong cause,
   old mission name). So a candidate is carried only if a second, **strict** check also
   passes: every claim of the reviewed answer (figure, name, cause, condition) must be backed
   by a quoted sentence of the current sections, and a renamed game term counts as outdated
   (`work/v2/strict_checks.jsonl`). Otherwise it is revalidated, reason `answer_not_verified`.

   **Amendment 2, before it ran (2026-11-20).** The judge measurement
   (`eval/LLM_MODELS.md`) replayed the strict check with `deepseek-flash` on the dev split:
   flash objected to 7 of the answers pro had verified, and a reading of them found at least
   two outdated answers (q055, q051) carried without a human review. So a carried answer
   now needs a second, independent check: the same strict check run by `deepseek-flash`
   over the same sections, on **both splits** (this is label quality control, applied alike
   to dev and test; nothing is tuned on it). An answer either judge does not verify goes
   back to review with reason `answer_not_verified`. This can only send answers to the
   reviewer, never carry more. Stage `second-check`, output
   `work/v2/strict_checks_flash.jsonl`.

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

## Wiki `f142383` (glossary fix, same day)

The only change after `b2cdaa9` is the DEFCON definition of the glossary, aligned with
`diplomacy#defcon` and the game's code in the six languages. Candidates keep `b2cdaa9` as
the revision they were re-assessed on: no other candidate depends on that sentence, and
bumping the revision would void decisions already taken. The one DEFCON question, q027 (to
revalidate), was already answered from `diplomacy#defcon` and is right; the fixed glossary
section was added by hand to its proposed sections, with a note, for the reviewer to keep
or untick.

## Models (2026-11-20, before steps 4 and the answer check ran)

Steps 1 to 3 ran with `deepseek-v4-pro` for every call. From step 4 on, each call uses the
model of its role (`eval/LLM_MODELS.md`): drafting on `deepseek-flash`, each judge on the
model its measurement against pro selects. The top-up drafts pro had already written before
the 402 are drafted again with flash, so that one model drafts all new questions.

## Where it stands (2026-11-20)

- Steps 1 to 3 done: 32 sections moved, 2 removed; of the 288 candidates, **69 carried**,
  **90 to revalidate**, 129 never reviewed (to review, with regenerated answers). The
  re-assessment found 122 old reference answers contradicted by the new wiki and 25
  incomplete; 41 of the 42 unanswerable questions now have an answer (all 10 out of scope,
  through the FAQ). The strict check moved 13 would-be carried answers back to review.
- Step 4 is incomplete: only 5 unanswerable questions remain, 37 must be drafted, and the
  DeepSeek account ran out of credit mid-run (402). The calls already made are cached.
- Reasons for revalidation: `answer_contradicted` 43, `now_answerable` 21,
  `answer_not_verified` 13, `answer_incomplete` 11, `renamed_terms` 2, and one each of
  `now_unanswerable`, `question_invalid`, `source_removed`, `rejected_wrong_answer`.
