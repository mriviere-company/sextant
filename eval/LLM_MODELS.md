# LLM models of the evaluation tooling

Written on 2026-11-20, **before** the measurement it describes.

Until now every LLM call of the evaluation tooling (drafting questions, judging relevance,
re-assessing on wiki v2, checking claims) used `deepseek-v4-pro`, by default and without a
measurement. Two facts make that default doubtful:

- **Cost.** Pro costs 4.4× flash on input and 3.3× on output
  ([pricing page](https://api-docs.deepseek.com/quick_start/pricing), read 2026-11-20;
  `src/sextant/generation/pricing.py`). The calls made so far would have cost 9.17 $ at peak
  price with pro and 2.15 $ with flash; 88 % of it went to judges.
- **Pro is not the newer model.** `deepseek-flash` is DeepSeek-V4.1-Flash-1017;
  `deepseek-v4-pro` is DeepSeek-V4-Pro-0813 (same page). Every call disables thinking, so
  whatever reasoning advantage pro has is not used either.

## Roles

| Role | Calls | Model |
|---|---|---|
| `draft` | question ideas, rewriting into the six languages, new unanswerable questions | **flash**, without measurement: a person reviews every drafted question and answer |
| `relevance_judge` | which pooled sections answer a question (`pipeline.judge`, `topup.unanswered`) | measured |
| `reassessment` | re-assessment on a rewritten wiki (`migration.reassess`) | measured |
| `strict_check` | claim-by-claim check before a decision is carried over (`migration.strict_check`) | measured |
| `answer_judge` | served answer against the wiki (`consistency.judge_answer`) | follows the rule below |

Judges are not switched blindly because their verdicts become reference labels that nobody
re-checks: in the phase 1 review not one relevance label was changed by the reviewer, so a
judge error enters the dataset unseen. The answering model (`deepseek-flash` by default,
phase 3) is out of scope: phase 4 compares answer models.

The roles live in `sextant.llm.MODELS`. `SEXTANT_EVAL_MODEL=deepseek-v4-pro` forces one model
on every role, which replays version 1 of the set and the v2 re-assessment from the response
cache (both ran with pro everywhere).

## Measurement (`python -m sextant.eval.judge_models`)

- **Items.** The judge requests pro already answered (the response cache), for **dev-split**
  candidates only; the test split is not used. Each request is replayed unchanged except
  the model: `deepseek-flash`, thinking disabled, temperature 0, JSON mode.
  - relevance judge: the phase 1 judge calls (wiki snapshot `ef59d47`);
  - reassessment: the v2 re-assessment calls (`b2cdaa9`);
  - strict check: the v2 strict-check calls.
- **Decisions compared**, the ones code consumes, parsed by the same functions for both models:
  - relevance judge: each (question, shown section) relevant or not; `answerable`;
  - reassessment: `old_answer` (consistent / contradicted / incomplete / not applicable),
    `answerable`, `question_valid`;
  - strict check: consistent or not.
- An answer that stays unusable (not JSON after one retry) is its own class, so it counts as
  a disagreement.
- **Statistic.** Cohen's kappa between flash and pro for each decision; when both models
  give one constant answer, perfect agreement counts as 1. Reported with a 95 % bootstrap
  interval over questions (10,000 resamples, seed 42), raw agreement, the confusion table,
  and every disagreement.

## Rule

1. A judge switches to flash if, for **every** decision it feeds to code, kappa ≥ 0.80 on
   dev (point estimate). Otherwise it stays on pro.
2. The answer judge switches to flash only if both the reassessment and the strict check
   do: it does both jobs (compares claims with the wiki, decides whether the wiki answers),
   and no pro answers exist yet to compare it with.

0.80 is the usual floor of "strong" agreement (McHugh, 2012). Kappa against pro measures
whether switching would change the labels, not which model is right: a pass means the
labels barely move, a fail keeps the more expensive model rather than guess. The
disagreements are listed for a person to read; phase 4 calibrates the judge against hand
grades. Known limit: pro is not perfectly repeatable at temperature 0 either, and that noise
floor is not measured here.

## Result (2026-11-20)

Figures: [`eval/results/judge_models.md`](results/judge_models.md) (333 flash calls, about
0.43 $ off-peak). The rule gives:

| Role | Model | Why |
|---|---|---|
| `draft` | flash | no measurement needed (reviewed by a person) |
| `relevance_judge` | **flash** | kappa 0.805 on sections, 0.911 on answerability |
| `reassessment` | pro | kappa 0.536 on the old-answer verdict |
| `strict_check` | pro | kappa 0.604 |
| `answer_judge` | pro | follows the two claim judges |

Read with care:

- The relevance judge passes **narrowly**: 0.805 against 0.80, and the interval
  (0.751 to 0.857) straddles the threshold. Flash marks more sections relevant than pro
  (83 sections pro left out against 26 the other way). For new unanswerable questions this
  errs on the safe side: a question survives only if no section answers it.
- On the two claim judges, flash is **stricter** than pro, not sloppier: 33 of its 50
  reassessment disagreements turn pro's "consistent" into "incomplete" or "contradicted",
  and all 7 strict-check disagreements turn pro's "consistent" into "not consistent". The
  rule keeps pro anyway; it was written before the run and is not bent after it.
- `answerable` and `question_valid` of the reassessment have low kappas despite 99.3 % and
  96.5 % raw agreement: one class is rare, which deflates kappa. They do not change the
  outcome, decided by the old-answer verdict.
- The 7 strict-check disagreements are answers pro let through **without a human review**.
  Reading them, at least two are wrong (q055 still says "Moon Maker" where the wiki now says
  "Lunar"; q051 lets points go to every ship where only combat ships get them), and at
  least one flash objection is wrong (q043: "minus 10 %" and "90 %" agree). This led to
  amendment 2 of [`eval/dataset/MIGRATION_V2.md`](dataset/MIGRATION_V2.md).
