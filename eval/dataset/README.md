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

All LLM calls are cached (`eval/.llm-cache/`, not committed) and keyed by the full request;
`PROMPT_VERSION` in `src/sextant/eval/generation/prompts.py` names the prompts used.
The whole run took 694 calls to `deepseek-v4-pro`, 2.1 M input and 0.14 M output tokens, 81 %
of the input for the relevance judge ([`work/llm_usage.json`](work/llm_usage.json)).

## Known biases

- **Lexical overlap.** Questions are written by a model that has just read the answering
  section, so they tend to reuse its vocabulary more than real players would, which favors
  lexical retrieval (BM25). The prompts ask for player wording and the styles vary length,
  but the bias remains; real player questions (phase 6) are the correction.
- **Pooling.** A section no strategy ranks in its top 10 can never be added to the
  relevance judgement. Strategies outside the pool (hybrid, reranking) can only reorder
  pooled sections, so this bias is small for them, but it exists.
- **One judge model.** The same model family drafts the questions and judges relevance;
  the human review is the check on both.
- **Unanswerable questions** are verified against the pooled sections, not the whole wiki;
  the reviewer's knowledge of the game covers the rest.
