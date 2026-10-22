"""The German law extractor, on small XML in the gesetze-im-internet.de format."""

from provrag import gii

LAW = b"""<dokumente><norm><metadaten><jurabk>UStG</jurabk>
<standangabe><standtyp>Neuf</standtyp>
<standkommentar>Neugefasst durch Bek. v. 21.2.2005</standkommentar></standangabe>
<standangabe><standtyp>Stand</standtyp>
<standkommentar>zuletzt ge\xc3\xa4ndert durch Art. 5 G v. 29.6.2026</standkommentar>
</standangabe></metadaten></norm>
<norm><metadaten><enbez>\xc2\xa7 4</enbez><titel>Steuerbefreiungen</titel></metadaten>
<textdaten><text><Content><P>Steuerfrei sind: <DL>
<DT>8.</DT><DD><P>a) die Gew\xc3\xa4hrung von Krediten <DL><DT>1.</DT><DD>nested</DD></DL></P></DD>
<DT>9.</DT><DD><P>Grunderwerb</P></DD>
</DL></P></Content></text></textdaten></norm>
<norm><metadaten><enbez>\xc2\xa7 19</enbez>
<titel>Besteuerung der Kleinunternehmer</titel></metadaten>
<textdaten><text><Content>
<P>(1) Ein Umsatz ist steuerfrei, wenn der Gesamtumsatz <B>25 000</B> Euro
nicht \xc3\xbcberschritten hat.</P>
<P>(2a) Gesamtumsatz ist die Summe.</P></Content></text></textdaten></norm>
<norm><metadaten><enbez>\xc2\xa7 20</enbez><titel>Nicht gewollt</titel></metadaten></norm>
</dokumente>"""


def test_the_stand_date_dates_every_row():
    valid_from, rows = gii.norms(LAW, {"19": None})
    assert valid_from == "2026-06-29"
    assert {r["valid_from"] for r in rows} == {"2026-06-29"}


def test_paragraphs_are_cut_at_their_numbers_and_inline_markup_keeps_its_words():
    _, rows = gii.norms(LAW, {"19": None})
    assert [(r["part"], r["text"]) for r in rows] == [
        (
            "1",
            "Ein Umsatz ist steuerfrei, wenn der Gesamtumsatz 25 000 Euro nicht überschritten hat.",
        ),
        ("2a", "Gesamtumsatz ist die Summe."),
    ]
    assert rows[0]["heading"] == "Besteuerung der Kleinunternehmer"


def test_numbered_items_come_from_the_top_level_list_only():
    _, rows = gii.norms(LAW, {"4": ["8"]})
    assert [(r["section"], r["part"]) for r in rows] == [("4", "Nr. 8")]
    assert rows[0]["text"].startswith("a) die Gewährung von Krediten")
