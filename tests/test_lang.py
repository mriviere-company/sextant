import pytest

from sextant.generation.lang import detect_lang


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("Comment fabriquer ma première flotte ?", "fr"),
        ("Quels bâtiments faut-il pour une flotte ?", "fr"),
        ("How do I build my first fleet?", "en"),
        ("What does the shipyard need to build a fleet?", "en"),
        ("Wie baue ich meine erste Flotte?", "de"),
        ("Welche Gebäude brauche ich für den Werftbau?", "de"),
        ("¿Cómo construyo mi primera flota?", "es"),
        ("¿Cuántos planetas puedo colonizar con mi alianza?", "es"),
        ("Como posso construir a minha primeira frota?", "pt"),
        ("Qual é o custo de uma nave não tripulada?", "pt"),
        ("Как построить свой первый флот?", "ru"),
        ("Сколько стоит верфь", "ru"),
    ],
)
def test_detects_each_language(question: str, expected: str) -> None:
    assert detect_lang(question) == expected


@pytest.mark.parametrize("text", ["xyzzy", "123 456", "Flotte", ""])
def test_no_signal_or_tie_falls_back_to_french(text: str) -> None:
    assert detect_lang(text) == "fr"


def test_cyrillic_wins_over_latin_words() -> None:
    assert detect_lang("How to build флот") == "ru"
