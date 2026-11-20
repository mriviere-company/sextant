# Evaluation set

How the questions in `questions.jsonl` were made, and what to keep in mind when reading any
figure computed on them. Figures: [`stats.json`](stats.json) (written by
`python -m sextant.eval.review build`).

## Files

| File | What it is |
|---|---|
| `work/ideas.jsonl` | Question ideas drafted in French by an LLM, per article, per pair of linked articles, and out of the wiki's scope |
| `work/plan.jsonl` | The ideas selected, with their question language, searched corpus and style |
| `work/realized.jsonl` | Each question written as a player of its language would, with its reference answer and a French gloss |
| `work/judgements.jsonl` | Sections pooled from every retrieval strategy, and those an LLM judge found answering |
| `work/llm_usage.json` | Calls and tokens spent by the generation |
| `candidates.jsonl` | 288 candidates for human review, **with their split already frozen** |
| `reviews.jsonl` | The reviewer's decisions (keep, correct, reject), exported from the review page |
| `questions.jsonl` | The evaluation set: kept and corrected candidates only, all `validated` |
| `stats.json` | Published figures: languages, kinds, splits, review outcomes |

## Method

1. **Ideas.** `deepseek-v4-pro` reads each of the 72 articles (French) and proposes questions
   of five kinds: factual, procedural, comparative, multi-section, and unanswerable (a
   question a player would ask about the topic that the article does not answer). Separate
   prompts draft questions that need two linked articles, and questions out of the wiki's
   scope altogether (account, payment, devices…).
2. **Selection.** 288 ideas are chosen for a fixed mix: per question language, 12 factual,
   9 procedural, 7 comparative, 9 multi-section and 7 unanswerable, plus 4 cross-lingual
   ones. That gives 42 unanswerable questions (14.6 %) and 24 cross-lingual ones. Ideas
   whose sections were already used are picked last, articles are used evenly (all 72 are
   covered), and an article's questions get different languages, so per-language figures
   are not computed on different topics.
3. **Realization.** Each idea is rewritten **directly in its target language** by reading the
   wiki sections *in that language*, in one of three player styles (short search-box query,
   natural sentence, or situated "I have… can I…"), with a reference answer and a French
   gloss for the reviewer. A cross-lingual question is written in its language from the
   sections of the other language's wiki, which is where it will be searched.
4. **Relevance pooling.** Every question is searched with the five first-stage strategies
   (BM25, PostgreSQL full text, three dense models); the union of their top 10 sections,
   plus the sections the idea came from, is shown to an LLM judge in wiki order, without
   saying which section is the source. Sections the judge finds answering are added to the
   proposed relevance; disagreements become review flags. This is TREC-style pooling: it
   finds the answering passages an LLM drafting from one article cannot know about (the
   wiki repeats facts across articles), so retrieval is not penalized for finding them.
5. **Frozen split.** Before any review, questions are split by **article** (every question
   drafted from one article in the same split, so a dev question never has a twin about the
   same passage in test), balancing language × kind × cross-lingual cells. The review can
   drop a question but never move it.
6. **Human review.** The reviewer, who knows the game, keeps, corrects or rejects each
   candidate on the review page, unticking any proposed section that does not answer. The
   page does not show the split. Only kept or corrected questions enter `questions.jsonl`.
   A decision is accepted only after the question has been on screen for 1.5 s, and each
   one records that time (`dwell_ms`); `stats.json` publishes the review pace.

**Incident, 2026-11-20.** The first review pass recorded q001–q072 at a reading pace
(about 16 minutes, one correction, one rejection), then marked q073–q288 — 216
questions — as kept in 45 seconds, 0.2 s each, without unticking a single section. A check
of the timestamps before import caught it; with the reviewer's agreement those 216
decisions were discarded and the questions sent back for review, and the page gained the
minimum display time above. Nothing from the discarded pass entered the evaluation set.

All LLM calls are cached (`eval/.llm-cache/`, not committed) and keyed by the full request;
`PROMPT_VERSION` in `src/sextant/eval/generation/prompts.py` names the prompts used.
The whole run took 694 calls to `deepseek-v4-pro`, 2.1 M input and 0.14 M output tokens, 81 %
of the input for the relevance judge ([`work/llm_usage.json`](work/llm_usage.json)).

## Review outcome (2026-11-20)

Figures: [`stats.json`](stats.json).

- **159 of the 288 candidates reviewed** (q001–q159). The review order interleaves
  languages and kinds, so this prefix is balanced. **158 validated** (157 kept,
  1 corrected), 1 rejected. Review pace of the second pass: median 6.7 s per question.
- **Split:** 84 questions in dev, 74 in test. Monolingual answerable questions per language:
  9 to 12 in dev, 8 to 11 in test, below the 15 that rule 5 of the protocol needs to apply;
  per-language differences on these splits are indicative only. Cross-lingual questions:
  5 in dev, 8 in test, too few for more than an anecdote.
- **Three unanswerable questions look answered by the wiki:** q030 (the estimated fuel is
  shown before launch, `fleet_creation` step 3 and `fleet_movement` "Le carburant"), q108
  (a fleet can be recalled until it arrives, `fleet_movement`) and q140 (deleting an
  account is final, `account_deletion`); q071 is borderline (the wiki gives no calendar but
  says where to see it). They do not enter retrieval metrics (phase 2) and must be settled
  before refusal is measured (phase 4).
- **129 candidates (q160–q288) are not reviewed.** They keep their frozen split; reviewing
  them later can only add questions to dev and test, never move one.

## Known biases

- **Lexical overlap.** Questions are written by a model that has just read the answering
  section, so they tend to reuse its vocabulary more than real players would, which favors
  lexical retrieval (BM25). The prompts ask for player wording and the styles vary length,
  but the bias remains; real player questions (phase 6) are the correction.
- **Pooling.** A section no strategy ranks in its top 10 can never be added to the
  relevance judgement. Strategies outside the pool (hybrid, reranking) can only reorder
  pooled sections, so this bias is small for them, but it exists.
- **Relevance labels are LLM-assisted and were not changed by the reviewer.** The reviewer
  validated the questions and their reference answers, but kept every proposed section
  set as is (0 of the 136 answerable questions, `relevance_changed_by_reviewer` in
  [`stats.json`](stats.json)).
  The relevant sections are therefore the drafting sources plus the LLM judge's pooled
  additions; the judge is generous on broad questions, which lowers precision-like scores
  and makes recall harder for every strategy alike.
- **One judge model.** The same model family drafts the questions and judges relevance.
- **Unanswerable questions** are verified against the pooled sections, not the whole wiki;
  the reviewer's knowledge of the game covers the rest.
