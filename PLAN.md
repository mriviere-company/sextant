# Sextant — RAG multilingue évalué sur le wiki d'Area Universe

> Plan d'exécution. Suivre les phases dans l'ordre ; chaque phase se termine par des critères d'acceptation vérifiables avant de passer à la suivante. **Statut : validé le 2026-11-20 ; phase 0 terminée, outillage de la phase 2 terminé (benchmark en attente de la phase 1).**
> « Sextant » est un nom de travail.

---

## 1. Contexte et objectif

Les offres d'ingénieur IA à Montréal demandent presque toutes deux choses absentes du portfolio actuel : un **RAG** (recherche dans des documents avec une base vectorielle) et un **cadre d'évaluation des LLM** (recall, MRR, nDCG, fidélité, juge LLM, observabilité).

Sextant répond aux questions des joueurs d'Area Universe à partir du wiki officiel du jeu, en citant ses sources, dans la langue du joueur. **Le sujet est l'évaluation autant que le RAG** : chaque choix (découpage, recherche lexicale, vectorielle ou hybride, reranking, modèle, prompt) est mesuré, comparé et protégé par une porte de CI.

Pourquoi ce corpus :
- **Il t'appartient et il est déjà public** (areauniverse.com/wiki) : on peut le publier dans un dépôt public sans question de licence.
- **Il est multilingue** : 72 articles en 6 langues (fr, en, de, es, pt, ru), environ 32 000 mots par langue, avec titre, catégorie, tags, résumé, articles liés et sections ancrées (`<h2 id="…">`). Les citations peuvent pointer vers `areauniverse.com/wiki/<slug>#<section>`.
- **Il a de vrais utilisateurs** : intégré au jeu (phase 6), Sextant servira de vrais joueurs, et l'entité `WikiFeedback` (vote utile / pas utile par article) existe déjà pour mesurer l'usage réel.

## 2. Architecture cible

```
wiki (YAML ×6 langues) → ingestion → découpage par section → embeddings locaux ─┐
                                                       └→ index plein texte ─────┤
                                                                                  ▼
question → recherche hybride (vectorielle + BM25, fusion RRF) → reranker → top-k → LLM → réponse citée
                                                                                  │
                                                            traces, coûts, latences ┘
```

- **Python 3.12, FastAPI, Pydantic v2, uv, pytest, ruff, mypy** (mêmes standards que vigil).
- **Embeddings locaux multilingues** (famille bge-m3 ou multilingual-e5) : aucun coût d'API, reproductibles en CI.
- **PostgreSQL + pgvector** (index HNSW) pour le vectoriel, **recherche plein texte PostgreSQL** pour le lexical, fusion par *reciprocal rank fusion*, **reranker cross-encoder** en option.
- **Génération derrière une interface** : Claude (Anthropic), DeepSeek (compatible OpenAI) et une doublure déterministe pour les tests. Réponse obligatoirement citée ; refus explicite quand le wiki ne contient pas la réponse.
- **Docker Compose** pour la stack locale (API + Postgres/pgvector).

## 3. Contrat d'API (à figer en phase 0 dans `docs/api.md`)

- `POST /v1/ask` : `{ "question": str, "lang"?: str, "top_k"?: int }` → `{ "answer": str, "citations": [{ "slug", "section", "url", "lang" }], "refused": bool, "latency_ms", "usage": { "input_tokens", "output_tokens", "cost_usd" } }`
- `POST /v1/search` : recherche seule (sans génération), pour le débogage et l'évaluation.
- `GET /v1/health`.

## 4. Structure du dépôt

```
corpus/          instantané du wiki (YAML), script de rafraîchissement, corpus normalisé (JSONL)
sextant/         ingestion, chunking, retrieval, generation, api
eval/            jeu de questions (versionné), métriques, juge LLM, rapports
eval/results/    résultats commités (JSON + rapport Markdown) — source de vérité des chiffres du README
infra/           docker-compose, migrations SQL
.github/         CI
```

## 5. Phases d'exécution

Chaque phase indique le modèle et l'effort conseillés pour l'exécuter (Haiku 5.5 → Sonnet 5.5 → Opus 5.5 → Fable 5.2).

### Phase 0 — Fondations · *Sonnet 5.5, medium* · ✅ terminée le 2026-11-20
- [x] Dépôt, `uv`, Makefile (`make check`, `make ingest`, `make lint`, `make test`…), CI (ruff, mypy `--strict`, pytest, contrôle du corpus, gitleaks sur tout l'historique)
- [x] Instantané du wiki dans `corpus/` (révision source notée) + script de rafraîchissement depuis Area Reborn
- [x] Ingestion : YAML → articles typés (slug, langue, titre, catégorie, tags, résumé, sections) ; HTML → Markdown léger (listes, tableaux avec en-têtes), conversion vérifiée sans perte mot à mot sur tout le corpus
- [x] Découpage par section `<h2>` (plafond 300 mots ; les gros tableaux sont coupés par lignes en répétant leur en-tête), identifiants stables et URL de citation
- [x] `.env.example`, `.gitignore`, contrat d'API figé dans `docs/api.md`

**Constat :** les ancres de sections sont traduites (`#principe` / `#principle`), mais chaque article a exactement la même structure de sections dans les 6 langues. L'alignement inter-langues se fait donc par **position de section** (`section_index`), vérifié à l'ingestion. Résultat : 2 289 morceaux, 374 sections par langue (`corpus/processed/stats.json`).

**Critères :** 72 articles × 6 langues ingérés sans perte ; tests du parseur et du découpage ; CI verte. ✅

### Phase 1 — Jeu d'évaluation · *Opus 5.5, high (conception) ; Matthieu valide*
- [ ] Génération de questions candidates par LLM à partir des sections (factuelles, procédurales, comparatives, multi-sections)
- [ ] Questions **sans réponse** dans le wiki (~15 %) pour mesurer le refus
- [ ] Questions **inter-langues** (question en anglais, réponse seulement dans un article français, etc.)
- [ ] Outil de validation humaine : Matthieu, qui connaît le jeu, accepte, corrige ou rejette chaque question et sa réponse de référence
- [ ] Découpage dev / test figé et versionné ; le test n'est jamais utilisé pour régler le système

**Critères :** au moins 150 questions validées à la main, chacune avec ses sections attendues et une réponse de référence ; statistiques du jeu (langues, types) publiées.

### Phase 2 — Recherche et benchmark · *Opus 5.5, high* · 🟡 outillage terminé, benchmark en attente du jeu d'évaluation
- [x] Embeddings locaux (ONNX via `fastembed` : MiniLM, mpnet, e5-large multilingues) + pgvector (HNSW cosinus) ; plein texte PostgreSQL par langue ; fusion RRF ; reranker cross-encoder bge-reranker-v2-m3 (int8)
- [x] **Changement de périmètre :** la recherche lexicale de référence est un **BM25 écrit à la main** (racinisation Snowball par langue), car le classement plein texte de PostgreSQL (`ts_rank_cd`) n'a pas d'IDF. Le plein texte PostgreSQL reste mesuré comme stratégie à part (`pg_fts`).
- [x] Harnais d'évaluation : hit@k, recall@k, precision@k, MRR, nDCG@10, au niveau de la **section** (indépendant de la langue), par langue et par type de question ; bootstrap apparié pour décider si un écart est réel
- [x] Règles de décision fixées **avant** toute exécution : [`eval/PROTOCOL.md`](eval/PROTOCOL.md)
- [ ] Benchmark comparatif **BM25 / plein texte / vectoriel / hybride / hybride + reranker** sur le dev, puis une seule exécution sur le test — dès que la phase 1 a produit les questions
- [ ] Latence de recherche p50 / p95 par configuration (mesurée par le benchmark)

**Critères :** rapport commité dans `eval/results/` ; configuration retenue justifiée par les chiffres ; biais connus documentés.

### Phase 3 — Génération et API · *Sonnet 5.5, medium*
- [ ] Interface fournisseur (Claude, DeepSeek, doublure) ; budgets de temps et de tokens ; suivi du coût par requête
- [ ] Prompt avec citations obligatoires, réponse dans la langue de la question, refus si le contexte ne suffit pas
- [ ] Garde-fous : citations validées contre le contexte fourni, injection de prompt via la question
- [ ] API FastAPI `/v1/ask`, `/v1/search`, `/v1/health` ; logs JSON avec identifiant de requête

**Critères :** tests du contrat d'API avec la doublure ; aucune citation inventée possible (vérifiée par le code, pas seulement par le prompt).

### Phase 4 — Évaluation de la génération · *Opus 5.5, high*
- [ ] Vérifications déterministes : précision et rappel des citations, exactitude du refus, langue de la réponse
- [ ] **Juge LLM** avec grille explicite : fidélité au contexte, exactitude par rapport à la référence, complétude
- [ ] **Calibration du juge** : Matthieu note à la main ~50 réponses ; accord juge-humain mesuré (kappa de Cohen) avant de faire confiance au juge
- [ ] Comparaison de modèles (par exemple Claude Haiku, Claude Sonnet, DeepSeek) : qualité, latence p95, coût pour 1 000 questions

**Critères :** rapport commité ; chaque chiffre du README renvoie à un fichier de `eval/results/`.

### Phase 5 — Portes de CI et observabilité · *Sonnet 5.5, medium*
- [ ] Évaluation de la recherche à chaque PR (sans LLM, gratuite) ; échec si une métrique baisse au-delà d'un seuil par rapport à la référence
- [ ] Évaluation de la génération à la demande ou la nuit (clé d'API en secret GitHub), rapport en artefact
- [ ] Traces par étape (recherche, rerank, génération) avec OpenTelemetry ; tableau de bord des coûts et latences
- [ ] gitleaks sur tout l'historique, Trivy sur l'image

**Critères :** une régression volontaire de la recherche fait échouer la CI.

### Phase 6 — Mise en production dans Area Universe · *Sonnet 5.5, medium (dépôts privés)*
- [ ] Bouton « Demander au wiki » dans Area Reborn, réponses citées avec liens vers les articles
- [ ] Optionnel : les bots du jeu (python-ia) s'appuient sur Sextant pour répondre aux questions de règles
- [ ] Boucle de retour : votes des joueurs sur les réponses, questions non résolues ajoutées au jeu d'évaluation après validation

**Critères :** chiffres d'usage réel (nombre de questions, taux de réponses jugées utiles) publiables dans le README sans données personnelles (Loi 25).

### Phase 7 — Serveur MCP et vitrine · *Sonnet 5.5, medium*
- [ ] Outil MCP `search_wiki` / `ask_wiki` pour les assistants compatibles
- [ ] README orienté recruteurs et outils de tri par IA : « At a glance », résultats mesurés, compétences avec preuves, `llms.txt`

**Critères :** un assistant MCP interroge le wiki ; README relu.

## 6. Standards transverses (rattachés à une phase)

| Standard | Phase propriétaire |
|---|---|
| Typage partout, Pydantic à chaque frontière, ruff + mypy stricts | 0 |
| Aucune clé ni donnée personnelle dans le dépôt ; `.env.example` | 0 |
| Seuils de décision fixés avant chaque benchmark | 2 et 4 |
| Chaque chiffre publié renvoie à un fichier de résultats commité | 2, 4, 7 |
| Coût par requête suivi et plafonné | 3 |
| Commits conventionnels qui expliquent le pourquoi | toutes |

## 7. Coûts

- Embeddings, recherche et évaluation de la recherche : **0 $** (modèles locaux, CI gratuite sur dépôt public).
- Génération et juge : quelques dollars pour l'ensemble des campagnes d'évaluation, plafonnés par un budget dans le code.
- Aucune infrastructure permanente avant la phase 6 ; en production, réutilisation du VPS d'Area Universe.

## 8. Décisions ouvertes

1. Nom définitif du projet.
2. Fournisseurs LLM : Claude seul, DeepSeek seul, ou les deux (recommandé : les deux, pour la comparaison qualité / coût).
3. Clé d'API pour les évaluations de génération : en secret GitHub sur le dépôt public, ou campagnes lancées en local.
4. Phase 6 : intégration dans le jeu dès la fin de la phase 4, ou après la vitrine.

## 9. Définition de « terminé »

Un recruteur ou un outil d'IA qui ouvre le dépôt voit en moins d'une minute : ce que fait Sextant, un tableau comparatif des stratégies de recherche, la qualité des réponses mesurée et calibrée, le coût et la latence, et la preuve d'un usage réel par les joueurs d'Area Universe.
