# API contract

Frozen in phase 0; implemented in phase 3. This file is the source of truth for endpoints
and schemas: code and tests follow it, and any change is made here first.

All bodies are JSON (UTF-8). Every response carries an `X-Request-Id` header (taken from the
request when present, generated otherwise).

## `POST /v1/ask`

Answer a question from the wiki, with citations.

Request:

```json
{ "question": "Comment fabriquer ma première flotte ?", "lang": "fr", "top_k": 5 }
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `question` | string, 3–500 chars | yes | |
| `lang` | `fr` \| `en` \| `de` \| `es` \| `pt` \| `ru` | no | Language of the answer. Detected from the question when absent. |
| `top_k` | integer, 1–20 | no | Chunks given to the model. Default set by the benchmark (phase 2). |

Response `200`:

```json
{
  "answer": "Construisez d'abord un Chantier spatial… [1]",
  "refused": false,
  "citations": [
    {
      "n": 1,
      "chunk_id": "fr:first_fleet#prerequis:0",
      "title": "Première flotte — Ce qu'il vous faut avant",
      "url": "https://www.areauniverse.com/wiki/first_fleet#prerequis",
      "lang": "fr"
    }
  ],
  "latency_ms": 820,
  "usage": { "input_tokens": 1450, "output_tokens": 120, "cost_usd": 0.0009 }
}
```

- `answer` cites its sources as `[n]`, each `n` present in `citations`.
- Every citation refers to a chunk that was actually given to the model; the server drops
  any other reference before responding (checked in code, not only asked in the prompt).
- `refused: true` when the wiki does not contain the answer: `answer` then says so and
  `citations` is empty.

## `POST /v1/search`

Retrieval only, without generation (debugging and evaluation).

Request: `{ "query": string, "lang"?: string, "top_k"?: integer }`

Response `200`:

```json
{
  "results": [
    { "chunk_id": "fr:first_fleet#prerequis:0", "score": 0.83, "title": "…", "url": "…", "lang": "fr", "text": "…" }
  ],
  "latency_ms": 35
}
```

## `GET /v1/health`

`200 { "status": "ok", "corpus_chunks": 2289, "index": "ready" }`, or `503` with
`"index": "loading"` while the index is not ready.

## Errors

Every error uses one envelope:

```json
{ "error": { "code": "invalid_request", "message": "question: too short", "request_id": "…" } }
```

| Status | `code` |
|---|---|
| 400 / 422 | `invalid_request` |
| 429 | `rate_limited` (with `Retry-After`) |
| 502 | `upstream_error` (LLM provider failed) |
| 503 | `unavailable` (index loading, budget exhausted) |
| 504 | `timeout` (time budget exceeded) |
