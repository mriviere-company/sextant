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

## Wiki `4da9931` (daily-objectives bonus, same day; written before it ran)

Two more commits after `b2cdaa9`: `f142383` (glossary, above) and `4da9931`, which restores
the bonus for completing all of the day's objectives with a new rule (the average reward of
those objectives, paid by the next daily report; the fixed +250 PDG is gone). Six sections
change in the six languages (`quests#recompense`, `daily_report#quetes`,
`getting_started#a-surveiller`, `tips#social`, `war_points#gagner`, the glossary); no anchor
moves, no section is added or removed.

Stage `update` (`--old-chunks` the previous `chunks.jsonl`):

1. **Touched candidates**: those whose relevant or source sections changed, plus those named
   with `--also` (here q266, the one quest question citing none of them; found by searching
   the questions and answers for quests, objectives and 250).
2. **Re-assessment** of their current answer against the new wiki, by the reassessment
   judge (pro), over freshly pooled sections plus their own.
3. **Code decides**: an answer the new wiki still backs fully is left untouched, revision
   included, so a decision taken on it stays valid; a carried one must also pass both strict
   checks (pro and flash). Any other gets the regenerated answer, reason `wiki_updated` and
   revision `4da9931`, which voids a decision taken earlier: carried and revalidated
   candidates go to revalidation, unreviewed ones stay to review.

**Amendment, after the stage ran (2026-11-20).** The re-assessment left q068 untouched
although its answer still promised the removed "bonus of 250 PDG" (its own note said the
bonus had changed), and regenerated a wrong answer for q168 ("complete the 3 missions to get
250 PDG"). Both strict checks, run on all 24 touched answers, reject both. So step 3 now
requires the two strict checks for every touched answer it would leave alone, not only for
carried ones (code updated). The checks also reject q132 (an unsupported name for the
alliance bonus, older than this commit; it was already to revalidate and stays as it is)
and, by flash only, q027 on "DEFCON 1 is a low alert", which the author confirms.

Outcome: 24 candidates touched, 4 changed by the stage (q006, q027, q112, q168), q068 sent
back by the amendment. The answers of **q068 and q168 are written by hand** from
`quests#recompense`, because the judge kept rebuilding them on the old bonus; both pass the
two strict checks, and their card says so. They carry revision `4da9931`; the only
decisions already taken on v2 (q001 to q004) are not affected. Re-assessments:
`work/v2/reassessments_4da9931.jsonl`.

**Wiki ahead of the game** (until the deployment of 2026-11-20, see below). The bonus the wiki now describes is only paid in production once
this branch and its migration are deployed. Reference answers follow the wiki, which is the
system's only source: until the deployment, an answer quoting the new bonus agrees with the
wiki but not yet with the live game.

## Main `df6465b` (Discord sections restored; reindex pending)

The author's release notes for `b2cdaa9` said the game sends no Discord alert for an
approaching enemy fleet, and the two removed sections (`notifications#discord`,
`alliance_basics#discord`) seemed to agree. **That was wrong**: the alert exists in the game
since 2026-11-16. The rewrite, merged into Area-Reborn `main` (`beaca67`, `219433a`,
`df6465b`, the same wiki as `b2cdaa9`, `f142383`, `4da9931` otherwise), restores both
sections, each as the last section of its article (no other section moves), and mentions
linking a Discord account in *Mes options* in `faq#contact` and `interface_guide`; checked
in the six languages.

Not indexed yet, at the author's request: the public wiki shows these changes only after
the deployment, and the corpus will be refreshed then (Sextant reads the repository's YAML,
so it could be done before). Until then:

- **q087** (to revalidate: its regenerated answer drops the Discord linking) and **q201**
  (made unanswerable when its section disappeared; its answer, 30 minutes per planet, is
  right) carry a note on their card: not to be validated before the reindex. The author
  confirms that their v1 answers still hold; the update stage will re-assess both.
- **Probe p12** now expects the alert to exist. On corpus `4da9931`, which lacks the
  section, the system's refusal is what the indexed wiki supports, not the game.

## Production `df6465b` (2026-11-20 evening; written before the stage ran)

The author reports the rewritten wiki in production since 2026-11-20 (`df6465b` on `main`),
and checked that the public API `/api/public/wiki` serves the repository's content in the
six languages. The caveat above about the bonus (wiki ahead of the game) no longer applies.

- **Corpus**: refreshed at `df6465b`, 2,575 chunks; against `4da9931`, 12 chunks changed and
  12 added, in exactly four sections (`notifications#discord` and `alliance_basics#discord`
  restored, `faq#contact`, `interface_guide#navigation`). Rebuilt from scratch (`--full`) at
  the author's request. An incremental sync gives the same vectors (an embedding depends on
  the text only), but the benchmarks use full rebuilds anyway.
- **Update stage**, with three additions:
  - `--also q157,q167,q254`: they became unanswerable on `b2cdaa9`, while the author states
    no section was removed; a second look, by the same rules.
  - `--hint q041=defense#temps`: the author states all 42 former unanswerable questions now
    have an answer; 41 did on `b2cdaa9`, and the last one, q041 (construction time of a
    turret, in Russian), is answered by the defense table (2.4 s per laser turret, divided by
    the production speed), a section the earlier judge was never shown. A hint adds sections
    to what the judge sees; it decides nothing.
  - `--restore q087,q201`: the author confirms their v1 answers (the Discord fleet alert).
    The v1 answer is put back and re-assessed like any other; only if the re-assessment and
    both strict checks agree is it kept: carried for q087 (reviewed in v1), to review for
    q201 (never reviewed). Otherwise the usual update applies.

Outcome (`work/v2/reassessments_df6465b.jsonl`): 9 candidates touched (the 3 named, 2
restored, q041, and q063, q199, q286 through the changed sections), 7 changed:

- **q087** restored and carried (its v1 decision holds again); **q201** restored, to review.
- **q041** now answerable (factual, `defense#temps`), to revalidate: all 42 former
  unanswerable questions now have an answer, as the author said.
- **q157** (no direct reward for the Points ranking), **q199** (report names) and **q254**
  regenerated; **q167** stays unanswerable (its "Product Army" no longer exists).
- The regenerated answers pass both strict checks, except q254 by flash: its claim that no
  "transfer to port" operation exists rests on an absence no sentence can back; its card
  says so.

## Main `9a80d9d2` (merchants and war points, 2026-11-21; written before the stage ran)

In production since 2026-11-20 evening, checked by the author against `/api/public/wiki`.
Two sections change in the six languages, nothing else: `market#gain` (troops resold at
about 1.5 times their training cost: Legionnaire 27, Scientist 110, Mecha 130 Bitcoins, no
longer 80, 300 and 1,000; war points for a sale) and `war_points#gagner` (1 PDG per 5,000
Bitcoins of base value, the same on arrival and from the merchant's orbit). Checked against
the game code at that commit (`GameConstants::RESOURCE_TRADE_PRICES`,
`TraderSaleCalculator`): prices, `round(base / 5000)` with +10 % per level of the alliance
research, and +5 % per level of « Accords marchands » on Bitcoins only, all match.

Update stage as before; `--also q102,q165,q217,q271,q293` adds the merchant questions that
cite neither section (found by searching questions for merchants, selling and war points).
q293 is one of the new unanswerable questions: drafted because the previous wiki gave no
troop prices, it now has an answer (27 Bitcoins). Old figures are searched for in every
reference answer and in the served answers, which are checked again with two new probes.

Outcome (`work/v2/reassessments_9a80d9d.jsonl`): 12 candidates touched, 4 changed, all
four regenerated answers passing both strict checks:

- **q293** (selling a Legionnaire) now answerable: 27 Bitcoins; 35 unanswerable questions
  remain.
- **q124** (carried) back to revalidation: the re-assessment finds it incomplete (it leaves
  out the production lost when storage is full).
- **q068**: same substance in a regenerated wording (the strict checks no longer backed the
  worked example of the hand-written version on the sections pooled this time).
- **q230** (all ways to earn war points) regenerated; to review.
- No reference answer quotes the old troop prices or the old war-point scale (searched in
  every answer and its French gloss, in the six languages).

**Leftovers in the wiki.** Two passages the commit did not touch still say a sale brings
"a few war points", without the scale, in the six languages: the glossary entry *Marchand*
and `market#vendre` ("vous recevez des Bitcoins et quelques Points de Guerre"). The served
answer to q271 repeats the latter. Reported to the author and fixed in `f8e93c1a`, merged into `main` (see below).

## Main `99afafd2` (taxes, 2026-11-21; written before the stage ran)

In production since 2026-11-21 around 2 a.m. Paris time, checked by the author against
`/api/public/wiki`. One sentence changes, in `daily_report#contenu` in the six languages:
the alliance tax is taken from the workers' income **after** the peace tax, if any.
Checked against the game code at that commit (`DailyTaxCalculator`): each lost peace takes
its rate from what is left after the previous one, then the alliance tax takes
`remaining × t / (100 + t)`. The author's worked example (50,000 Bitcoins, 20 % peace,
10 % alliance: 10,000 then about 3,636) matches the code but is **not** in the wiki, nor is
the rule for several peaces: reference answers follow the wiki only.

No candidate asks how the taxes are computed. Update stage with
`--also q003,q022,q064,q082,q084,q116,q165,q232`: the questions whose question or answer,
in any language, mentions taxes, tribute, peace, the treasury or the report's balance
(found by searching), besides q258 and q288, which cite the changed section. Two probes are
added for the served answers: the order of the taxes with the author's figures, and
whether the tax is taken twice.

Outcome (`work/v2/reassessments_99afafd.jsonl`): the 10 answers hold (re-assessment and both
strict checks); none computes the alliance tax, so none needed the new order. No reference
answer computes a tax on gross income. The set has **no question on the order of the
taxes**: one could be added, to review like any new question.

## Main `f8e93c1a` (merchant leftovers fixed, 2026-11-21; written before the stage ran)

The two leftovers found at `9a80d9d2` are fixed in the six languages and fast-forwarded to
`main` at the author's request: the glossary entry *Marchand* and `market#vendre` now give
the scale (1 war point per 5,000 Bitcoins of base value) instead of "a few war points". Not
yet deployed: the corpus follows `main`, and no anchor changes, so links stay valid.
Update stage as before, with `--also q271` (the question whose served answer repeated the
old wording) besides the candidates citing the two sections.

Outcome (`work/v2/reassessments_f8e93c1.jsonl`): 13 candidates touched, 12 hold. q132 (in
Russian; why join an alliance first, and what the bonus is called) went back to
revalidation: both strict checks reject its claim that the +20 % "is called the alliance
bonus", and the regenerated answer kept it. The wiki gives that bonus no name, so its answer
is **written by hand**: the +20 % and the access to diplomacy and alliance research, and
that the wiki names no such bonus. Pro verifies it; flash cannot back the absence of a
name with a quote, as for q254, and the card says so. The served answer to q271 now gives
the scale.

**Production check (2026-11-21, 22:30 UTC).** After the redeployment (build of 22:27:56
UTC), every article the public API serves (`/api/public/wiki/{slug}`, 73 articles × 6
languages) was compared with the corpus: titles and bodies are identical, whitespace aside.
A first check, after an earlier deployment, had found the build older than `f8e93c1a` and
the old merchant wording still served.

## Models (2026-11-20, before steps 4 and the answer check ran)

Steps 1 to 3 ran with `deepseek-v4-pro` for every call. From step 4 on, each call uses the
model of its role (`eval/LLM_MODELS.md`): drafting on `deepseek-flash`, each judge on the
model its measurement against pro selects. The top-up drafts pro had already written before
the 402 are drafted again with flash, so that one model drafts all new questions.

## Where it stands (2026-11-21, wiki `f8e93c1a`)

- Steps 1 to 3 done: 32 sections moved, 2 removed. The re-assessment found 122 old
  reference answers contradicted by the new wiki and 25 incomplete; 41 of the 42
  unanswerable questions now have an answer (all 10 out of scope, through the FAQ). The
  strict check (pro) moved 13 would-be carried answers back to review, the second check
  (flash, amendment 2) 14 more: q021, q023, q025, q032, q043, q051, q055, q066, q074, q118,
  q125, q134, q136, q150 (8 dev, 6 test).
- Step 4 done, short of target by 2: **35 new unanswerable questions** (q289 to q323),
  drafted by flash, for **40** in all (7 per language except French and English, 6 each); on `df6465b`, q041, q157, q201 and q254 left that
  count, and on `9a80d9d2` q293: it is now 35.
  Flash drafted 237 ideas; the relevance judge left 65 that no section answers; written in
  their language, about one in three was judged answerable again and dropped
  (`work/v2/topup_tried.json`: 52 ideas tried, 35 kept). The stage ran three times, each
  run drawing only ideas not tried before; 13 untried ideas remain.
- **323 candidates: 55 carried, 104 to revalidate (4 already done on v2), 164 to review**
  (129 never reviewed, 35 new); 35 unanswerable (34 of the new ones and q167). Reasons for revalidation: `answer_contradicted` 43, `answer_not_verified` 27,
  `now_answerable` 21, `answer_incomplete` 11, `renamed_terms` 2, and one each of
  `now_unanswerable`, `question_invalid`, `source_removed`, `rejected_wrong_answer`.
- Served answers against the wiki: [`eval/results/v2_answer_consistency.md`](../results/v2_answer_consistency.md)
  (19 probes and the 154 dev questions, `deepseek-flash` answering, pro judging, wiki
  `4da9931`). See below.

## Served answers against wiki v2

Run on `99afafd2`: [`eval/results/v2_answer_consistency.md`](../results/v2_answer_consistency.md)
(24 probes, p23 and p24 added for the taxes, and the 154 dev questions; `deepseek-flash`
answering, pro judging). No probe repeats a fact the rewrites corrected, and no served
answer computes the alliance tax on gross income: with 50,000 Bitcoins, 20 % peace and
10 % alliance, the system takes the peace tax first, then about 3,636 on the 40,000 left
(p23); it says the tax is taken once (p24). Flags, read one by one:

| Item | Judge | Reading |
|---|---|---|
| `q021` | missed answer | **Right**, fifth run in a row: the system refuses; the wiki gives Tacticien +10 % in the first round, arena included. |
| `q060` | contradicted | **Partly right**: the answer says the wiki does not detail the tournament rewards, which it does. |
| `p23` | contradicted | **Judge error**: the answer's arithmetic is right; the worked example is not in the wiki, and the judge cannot check it. |
| `p10` | contradicted | **Judge error**: the answer is the wiki's, and the judge's note says so. |

This run calls q250's refusal correct, where the previous four called it a missed answer:
both the served answers and the judge vary from run to run, so one run is a sample, not a
verdict on a question. Re-run on `f8e93c1a` (merchant leftovers fixed): q271 now gives the scale; new flags are
judge errors (p22 objects to an ambiguous sentence in a right answer, q027 again to "DEFCON
1 is a low alert").
