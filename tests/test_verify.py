"""One test per verifier rule, on hand-made passages."""

import pytest

from provrag.ingest import Chunk
from provrag.verify import Claim, Draft, verify


def chunk(id, tier, body, valid_from="2011-08-29", valid_to=None):
    return Chunk(id, "src", tier, "NZ", "8", "1", "heading", body, valid_from, valid_to, False)


STATUTE = chunk("act:s8(1)@2011-08-29", "T1", "tax is charged at the rate of 15% on the supply")
OLD = chunk("act:s8(1)@2007-09-03", "T1", "at the rate of 12.5 percent", "2007-09-03", "2010-10-01")
GUIDE = chunk("ird:filing#2", "T2", "Your GST return is due by the 28th of the month.")
NOTE = chunk("notes:P01@2025-03-10", "T3", "The GST rate is 17.5% now and 15 days to file.")
RETRIEVED = {c.id: c for c in (STATUTE, OLD, GUIDE, NOTE)}
TODAY = "2026-10-19"


def draft(answer, *claims, refused=False):
    return Draft(
        answer=answer,
        claims=[Claim(text=t, chunk_ids=list(ids)) for t, ids in claims],
        refused=refused,
    )


def check(d, question="What is the GST rate?", day=TODAY, **kw):
    return verify(d, question, day, RETRIEVED, **kw)


def test_a_supported_answer_passes():
    assert check(draft("GST is 15 percent.", ("The rate is 15%.", [STATUTE.id]))) == []


def test_a_refusal_passes():
    assert check(draft("", refused=True)) == []


def test_an_answer_needs_a_claim_and_every_claim_a_citation():
    assert check(draft("GST applies.")) == [
        "an answer that is not a refusal needs at least one claim"
    ]
    assert "claim 1 cites no passage" in check(draft("x", ("GST applies.", [])))


def test_only_retrieved_passages_can_be_cited():
    errors = check(draft("15%", ("The rate is 15%.", ["act:s8(1)@2026-01-01"])))
    assert any("not retrieved" in e for e in errors)


def test_a_passage_out_of_force_on_the_day_is_refused():
    errors = check(draft("12.5%", ("The rate is 12.5%.", [OLD.id])))
    assert any("not in force on 2026-10-19" in e for e in errors)


def test_a_number_must_be_in_a_cited_passage_of_the_same_kind():
    assert check(draft("15%", ("The rate is 15%.", [GUIDE.id]))) != []
    errors = check(draft("15 days", ("You have 15 days.", [STATUTE.id])))
    assert any("15 (count:day)" in e for e in errors), "15% must not support 15 days"


def test_an_untrusted_note_is_never_a_source():
    errors = check(draft("17.5%", ("The rate is 17.5%.", [NOTE.id])))
    assert any("untrusted notes" in e for e in errors)
    assert any("17.5 (percent)" in e for e in errors)


def test_citing_a_note_beside_a_source_is_still_an_error():
    errors = check(draft("15%", ("The rate is 15%.", [STATUTE.id, NOTE.id])))
    assert errors == [f"claim 1 cites untrusted notes, which are never a source: {NOTE.id}"]


def test_without_the_notes_rule_a_note_can_support_a_number():
    assert check(draft("17.5%", ("The rate is 17.5%.", [NOTE.id])), notes_rule=False) == []


def test_numbers_in_the_answer_text_must_be_claimed():
    errors = check(
        draft("15%, and returns are due on the 20th.", ("The rate is 15%.", [STATUTE.id]))
    )
    assert errors == ["the answer states 20 (day_of_month), which no claim states"]


def test_section_references_and_the_questions_own_numbers_are_exempt():
    question = "Was the rate 15% on 1 October 2011?"
    answer = draft(
        "Yes, under section 8(1) it was 15% on 1 October 2011.",
        ("Section 8(1) sets the rate at 15% on 1 October 2011.", [STATUTE.id]),
    )
    assert check(answer, question=question) == []


@pytest.mark.parametrize("figure", ["$30", "$15", "3/23"])
def test_a_calculated_figure_has_no_source(figure):
    errors = check(draft(figure, (f"The GST is {figure}.", [STATUTE.id])))
    assert errors and "no cited passage contains" in errors[0]
