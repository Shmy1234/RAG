from ingest.table_normalizer import normalize_table_html

APPLE_SEGMENT_TABLE = """
<table id="segment-performance">
  <tr>
    <td colspan="3"></td>
    <td colspan="3">2024</td>
    <td colspan="3"></td>
    <td colspan="3">Change</td>
    <td colspan="3"></td>
    <td colspan="3">2023</td>
  </tr>
  <tr>
    <td colspan="3">Americas</td>
    <td>$</td><td>167,045</td><td></td>
    <td colspan="3"></td>
    <td colspan="2">3</td><td>%</td>
    <td colspan="3"></td>
    <td>$</td><td>162,560</td><td></td>
  </tr>
  <tr>
    <td colspan="3">Total net sales</td>
    <td>$</td><td>391,035</td><td></td>
    <td colspan="3"></td>
    <td colspan="2">2</td><td>%</td>
    <td colspan="3"></td>
    <td>$</td><td>383,285</td><td></td>
  </tr>
</table>
"""


def test_normalize_table_html_collapses_sec_layout_columns():
    table = normalize_table_html(
        APPLE_SEGMENT_TABLE,
        table_index=4,
        title="Segment Operating Performance",
        units="USD millions",
        section_path=("Item 7", "Segment Operating Performance"),
    )

    assert table.table_index == 4
    assert table.title == "Segment Operating Performance"
    assert table.units == "USD millions"
    assert table.section_path == ("Item 7", "Segment Operating Performance")
    assert table.headers == ("Segment", "2024", "2024 Change", "2023")
    assert table.rows[0].label == "Americas"
    assert table.rows[0].values == ("$167,045", "3%", "$162,560")
    assert table.rows[1].label == "Total net sales"
    assert table.rows[1].values == ("$391,035", "2%", "$383,285")
    assert table.source_locator.html_id == "segment-performance"


def test_normalize_table_html_rejects_layout_only_table():
    table = normalize_table_html(
        "<table><tr><td>Address</td><td>Zip code</td></tr></table>",
        table_index=0,
    )

    assert table is None
