from sextant.eval.consistency import Check, parse_verdict, render


def test_parse_verdict_keeps_contradictions_and_is_strict_on_unknown_values() -> None:
    verdict, items, note = parse_verdict(
        {
            "verdict": "contradicted",
            "contradictions": [{"claim": "eau", "wiki": "Bitcoins"}, "x"],
            "note": "n",
        }
    )
    assert verdict == "contradicted"
    assert items == ({"claim": "eau", "wiki": "Bitcoins"},)
    assert note == "n"
    assert parse_verdict({"verdict": "probably fine"})[0] == "contradicted"


def test_render_lists_only_flagged_answers() -> None:
    def check(cid: str, verdict: str) -> Check:
        return Check.model_validate(
            {
                "id": cid,
                "source": "probe",
                "lang": "fr",
                "question": "q",
                "answer": "a",
                "refused": False,
                "cited": [],
                "verdict": verdict,
            }
        )

    report = render(
        [check("p01", "consistent"), check("p02", "contradicted"), check("p03", "missed_answer")]
    )
    assert "Flagged (2)" in report
    assert "`p02`" in report
    assert "`p03`" in report
    assert "`p01`" not in report
