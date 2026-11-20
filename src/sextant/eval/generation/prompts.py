"""Prompts of the question-generation pipeline.

`PROMPT_VERSION` is recorded on every candidate: a prompt change produces new
cache keys, hence new candidates, and the version says which prompts made a
given evaluation set.

The pipeline drafts *ideas* in French (the reviewer's language) from whole
articles, then *realizes* each selected idea as a player would type it in the
target language, reading the source sections in the language of the corpus
being searched. Drafting from whole articles lets the model propose distinct
questions per article; realizing from the target-language text keeps each
question native rather than translated.
"""

from __future__ import annotations

PROMPT_VERSION = "2026-11-20.1"

LANG_NAMES = {
    "fr": "français",
    "en": "anglais",
    "de": "allemand",
    "es": "espagnol",
    "pt": "portugais",
    "ru": "russe",
}

_CONTEXT = (
    "Tu aides à construire le jeu d'évaluation d'un assistant qui répond aux questions des "
    "joueurs d'Area Universe (jeu de stratégie spatiale multijoueur) à partir du wiki officiel "
    "du jeu, en citant les sections utilisées. Les questions servent à mesurer si la recherche "
    "retrouve les bonnes sections et si l'assistant refuse quand le wiki ne contient pas la "
    "réponse. Un joueur qui connaît le jeu relira chaque question."
)

_QUESTION_RULES = """Règles pour chaque question :
- Elle est autonome : compréhensible sans avoir lu l'article. Jamais « selon le wiki », « dans \
cet article », « cette section ».
- Elle ressemble à ce qu'un vrai joueur demanderait, pas à un exercice scolaire.
- Elle n'a qu'une bonne réponse, que le texte fourni permet d'établir sans interprétation.
- Les questions d'un même article portent sur des informations différentes."""

IDEAS_SYSTEM = f"""{_CONTEXT}

À partir d'un article du wiki, propose des idées de questions, en français, de cinq types :
- "factual" : un fait précis (nombre, nom, condition, effet, durée, coût) énoncé dans une section.
- "procedural" : « comment faire … ? », dont la réponse est une démarche décrite dans l'article.
- "comparative" : compare deux éléments ou plus (vaisseaux, bâtiments, modes, missions, régimes, \
rôles…) dont l'article donne la différence.
- "multi_section" : la réponse exige des informations de deux sections différentes au moins ; \
aucune section ne suffit seule ("sections" contient donc au moins deux numéros).
- "unanswerable" : une question qu'un joueur poserait naturellement sur ce sujet, proche de \
l'article, mais dont la réponse N'EST PAS dans l'article, même partiellement (un détail, un \
chiffre, un mécanisme que l'article ne donne pas). Pas de piège grossier, pas de hors-sujet, \
pas de question dont la réponse se déduit de l'article (« peut-on le faire plus de N fois ? » \
quand l'article donne N a une réponse). Formulée simplement, comme un joueur.

{_QUESTION_RULES}

Quantités : jusqu'à 3 "factual", 2 "procedural", 2 "comparative", 2 "multi_section", \
2 "unanswerable". Ne propose un type que si l'article le permet vraiment : mieux vaut zéro \
idée d'un type qu'une idée forcée.

Pour chaque idée réponds :
- "kind" : le type ;
- "question" : la question, en français ;
- "answer" : la réponse de référence, en français, 1 à 3 phrases, complète, tirée uniquement de \
l'article (pour "unanswerable" : ce que l'article dit de proche et ce qui manque) ;
- "sections" : les numéros de TOUTES les sections qui contiennent la réponse ou une partie \
nécessaire (liste vide pour "unanswerable").

Réponds par un objet JSON : {{"ideas": [{{"kind": …, "question": …, "answer": …, \
"sections": […]}}]}}"""

CROSS_SYSTEM = f"""{_CONTEXT}

On te donne deux articles liés du wiki, A et B. Propose 1 ou 2 idées de questions, en \
français, dont la réponse exige à la fois une information d'une section de A ET une information \
d'une section de B : ni A seul ni B seul ne suffit.

{_QUESTION_RULES}

Pour chaque idée réponds :
- "question" : la question, en français ;
- "answer" : la réponse de référence, en français, 1 à 3 phrases, tirée uniquement des articles ;
- "sections" : les sections nécessaires, notées "A:2", "B:0"… (au moins une de A et une de B).

S'il n'existe pas de bonne question qui exige vraiment les deux articles, réponds \
{{"ideas": []}}. Format JSON : {{"ideas": [{{"question": …, "answer": …, "sections": […]}}]}}"""

OUT_OF_SCOPE_SYSTEM = f"""{_CONTEXT}

Voici la liste des articles du wiki (titre et résumé). Propose le nombre de questions demandé, \
en français, \
qu'un joueur d'Area Universe pourrait réellement poser à l'aide du jeu mais auxquelles le wiki \
ne répond certainement pas : compte et paiement, technique (appareil, navigateur, connexion), \
calendrier des serveurs, équipe du jeu, fonctionnalités que le wiki ne décrit pas. Varie les \
sujets ; pas de question hors du jeu (météo, cuisine…).

Pour chaque idée : "question" (en français) et "answer" (une phrase : pourquoi le wiki ne peut \
pas répondre). Format JSON : {{"ideas": [{{"question": …, "answer": …}}]}}"""

STYLES = {
    "short": (
        "très courte, comme tapée vite dans une barre de recherche : quelques mots ou une "
        "phrase brève, ponctuation facultative"
    ),
    "natural": "une phrase complète, au ton naturel et familier d'un joueur",
    "situated": (
        "partant de la situation du joueur (« j'ai … », « mon … », « je veux … »), puis la question"
    ),
}

REALIZE_SYSTEM = f"""{_CONTEXT}

On te donne une idée de question rédigée en français, sa réponse de référence, et les sections \
du wiki qui la justifient. Réécris la question et la réponse comme les écrirait un joueur dont \
la langue est {{lang_name}} ({{lang}}).

Règles :
- La question est écrite directement en {{lang_name}}, naturellement, pas comme une traduction. \
Style demandé : {{style}}.
- Ne recopie pas les phrases du wiki : reformule avec les mots d'un joueur. Les noms propres et \
termes du jeu restent ceux qu'un joueur voit dans le jeu.
- Le sens de la question ne change pas : même information demandée, même difficulté.
- La réponse de référence, en {{lang_name}}, est fidèle aux sections fournies (ou, si l'idée \
n'a pas de réponse dans le wiki, dit en une phrase que le wiki ne le précise pas et ce qui \
manque). 1 à 3 phrases.
- Donne aussi une traduction française fidèle de ta question et de ta réponse, pour le relecteur.

Format JSON : {{{{"question": …, "answer": …, "question_fr": …, "answer_fr": …}}}}"""

JUDGE_SYSTEM = """You judge relevance for a retrieval evaluation set built on the Area Universe \
game wiki. You get a player's question, a reference answer, and wiki sections labelled S1, S2… \
(possibly in another language than the question).

A section is RELEVANT when it states the answer, or a part of the answer that is needed (for \
questions that combine several facts). A section that only mentions the topic, or would merely \
help with a different question, is NOT relevant. Judge each section on its own text.

Also say whether the sections, taken together, contain a complete answer to the question.

Answer with one JSON object: {"relevant": ["S2", …], "answerable": true|false, \
"note": "<one short sentence, in French, only if something is surprising, else empty>"}"""
