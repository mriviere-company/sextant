"""Language detection for questions sent without `lang` (a pure function, no model).

Cyrillic letters mean Russian. Otherwise each language scores its function words (words
that are not shared with the others) and its characteristic letters; the best score wins,
and no signal or a tie goes to French, the default language of the site.
"""

from __future__ import annotations

import re

from sextant.models import Lang

FALLBACK_LANG: Lang = "fr"

_WORD = re.compile(r"[^\W\d_]+")
_CYRILLIC = re.compile(r"[Ѐ-ӿ]")


def _words(text: str) -> frozenset[str]:
    return frozenset(text.split())


_FUNCTION_WORDS: dict[Lang, frozenset[str]] = {
    "fr": _words(
        """le les une des du est sont pour comment quoi quel quelle quels quelles qui dans avec
        mon ma mes ce cette peux peut puis fais faire où combien pourquoi je ai il ne pas au aux
        sur nous vous"""
    ),
    "en": _words(
        """the is are how what which does do can my to of and with for i on where why when much
        many you it this that should need"""
    ),
    "de": _words(
        """der die das und ist sind wie was welche welcher welches kann ich mein meine meinen für
        mit nicht im ein eine wo warum wann baue bauen auf zu den dem viel wird"""
    ),
    "es": _words(
        """el los las una es cómo como qué cuál cuáles para con mi mis por dónde cuánto cuánta
        cuántos cuántas puedo hacer del se y"""
    ),
    "pt": _words(
        """os as uma é são como qual quais para com meu minha meus por onde quanto quantos quantas
        posso fazer dos das não você"""
    ),
}

_LETTER_WEIGHTS: dict[Lang, dict[str, int]] = {
    "fr": {"è": 1, "ê": 1, "à": 1, "ù": 1, "œ": 2, "â": 1, "î": 1, "ô": 1, "û": 1, "ç": 1},
    "en": {},
    "de": {"ß": 3, "ä": 1, "ö": 1, "ü": 1},
    "es": {"ñ": 3, "¿": 3, "¡": 3},
    "pt": {"ã": 3, "õ": 3, "ç": 1},
}


def _score(lang: Lang, text: str, words: list[str]) -> int:
    function_words = _FUNCTION_WORDS.get(lang, frozenset())
    score = sum(1 for word in words if word in function_words)
    return score + sum(text.count(char) * weight for char, weight in _LETTER_WEIGHTS[lang].items())


def detect_lang(text: str) -> Lang:
    """Guess the language of a question; French when there is no signal or a tie."""
    if _CYRILLIC.search(text):
        return "ru"
    lowered = text.lower()
    words = _WORD.findall(lowered)
    scores = {lang: _score(lang, lowered, words) for lang in _FUNCTION_WORDS}
    top = max(scores.values())
    winners = [lang for lang, score in scores.items() if score == top]
    if top == 0 or len(winners) != 1:
        return FALLBACK_LANG
    return winners[0]
