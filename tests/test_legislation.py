"""The statute extractor, on small hand-written XML in the site's format."""

from provrag import legislation


def act(*provs: str) -> bytes:
    return f"<act><body>{''.join(provs)}</body></act>".encode()


SECTION_8 = """
<prov><label>8</label><heading>Imposition of goods and services tax on supply</heading>
<prov.body>
  <subprov><label>1</label><para><text>A tax is charged at the rate of {rate} on the supply
    <citation>by a registered person</citation> of goods.</text></para></subprov>
  <subprov deletion-status="repealed"><label>2</label><para><text/></para></subprov>
  <subprov><label>3</label><para><text>Goods are supplied when</text>
    <label-para><label>a</label><para><text>invoiced; or</text></para></label-para>
    <label-para><label>b</label><para><text>paid.</text></para></label-para></para></subprov>
</prov.body>
<notes><history><history-note>Section 8(1): amended, on 1 October 2010</history-note>
</history></notes>
</prov>
"""


def test_subsections_render_with_paragraph_labels_and_without_history():
    rows = legislation.sections(act(SECTION_8.format(rate="12.5 percent")), ["8"])
    assert rows[("8", "1")] == {
        "heading": "Imposition of goods and services tax on supply",
        "text": "A tax is charged at the rate of 12.5 percent on the supply by a registered"
        " person of goods.",
    }
    assert rows[("8", "2")]["text"] == "[Repealed]"
    assert rows[("8", "3")]["text"] == "Goods are supplied when (a) invoiced; or (b) paid."
    assert not any("2010" in r["text"] for r in rows.values())


def test_only_wanted_sections_and_only_the_first_occurrence_are_kept():
    quoted = SECTION_8.format(rate="99 percent")
    rows = legislation.sections(act(SECTION_8.format(rate="15%"), quoted), ["8"])
    assert "15%" in rows[("8", "1")]["text"]
    assert legislation.sections(act(SECTION_8.format(rate="15%")), ["9"]) == {}


def test_a_repealed_section_keeps_a_stub():
    stub = '<prov deletion-status="repealed"><label>24</label><heading>Tax invoices</heading>'
    rows = legislation.sections(act(stub + "<prov.body/></prov>"), ["24"])
    assert rows == {("24", ""): {"heading": "Tax invoices", "text": "[Repealed]"}}


def test_intervals_extend_while_unchanged_and_close_on_change_or_removal():
    old = {"heading": "h", "text": "12.5 percent"}
    new = {"heading": "h", "text": "15 percent"}
    versions = {
        "2009-01-01": {("8", "1"): old, ("8", "2"): old},
        "2010-09-07": {("8", "1"): old, ("8", "2"): old},
        "2010-10-01": {("8", "1"): new},
    }
    rows = legislation.intervals(versions)
    spans = [(r["section"], r["part"], r["text"], r["valid_from"], r["valid_to"]) for r in rows]
    assert spans == [
        ("8", "1", "12.5 percent", "2009-01-01", "2010-10-01"),
        ("8", "2", "12.5 percent", "2009-01-01", "2010-10-01"),
        ("8", "1", "15 percent", "2010-10-01", None),
    ]
