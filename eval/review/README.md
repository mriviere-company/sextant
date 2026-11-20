# Review page

`index.html` is the page the reviewer uses, on a phone, to keep, correct or reject each
candidate of `eval/dataset/candidates.jsonl`. `candidates.json` is its data, rebuilt with
`make review-page`: question and reference answer in their language with a French gloss, the
proposed sections (sources first, then the judge's additions) with their French text, and the
review flags. The page never shows the split, and it accepts a decision only after the
question has been on screen for 1.5 s, recording that time as `dwell_ms`.

Decisions are stored one document per candidate (`reviews/<id>`) in the page's database when
it runs as a claude.ai artifact, where only the owner may write; opened as a plain file, it
keeps them in the browser. Either way, **Exporter** gives them as JSONL, and

```bash
uv run python -m sextant.eval.review import reviews.jsonl   # → eval/dataset/reviews.jsonl
make dataset                                               # → questions.jsonl, stats.json
```

turn them into the evaluation set. A correction made only in a question's French gloss is
refused by `make dataset`: the question in its own language must be corrected too (the page
can translate the French through Claude, for the reviewer to check).
