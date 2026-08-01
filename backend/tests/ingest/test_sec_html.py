from ingest.sec_html import extract_sec_html


def test_extract_sec_html_preserves_section_and_table_context():
    source = """
    <html><body>
      <div id="item-7">Item 7. Management's Discussion and Analysis</div>
      <div>Segment Operating Performance</div>
      <p>The following table shows net sales (dollars in millions):</p>
      <table id="segments">
        <tr><td colspan="3"></td><td colspan="3">2024</td><td colspan="3">2023</td></tr>
        <tr><td colspan="3">Americas</td><td>$</td><td>167,045</td><td></td><td>$</td><td>162,560</td><td></td></tr>
      </table>
    </body></html>
    """

    document = extract_sec_html(source)

    assert len(document.tables) == 1
    table = document.tables[0]
    assert table.title == "Segment Operating Performance"
    assert table.units == "USD millions"
    assert table.section_path[0].startswith("Item 7.")
    assert len(table.section_path) == 1
    assert table.rows[0].values == ("$167,045", "$162,560")
    assert document.blocks[-1].kind == "table"
    assert document.blocks[-1].table_index == 0


def test_extract_sec_html_ignores_inline_xbrl_hidden_content():
    source = """
    <html><body>
      <ix:hidden><ix:nonfraction name="us-gaap:Revenue">999</ix:nonfraction></ix:hidden>
      <p>Visible filing text.</p>
    </body></html>
    """

    document = extract_sec_html(source)

    assert [block.text for block in document.blocks] == ["Visible filing text."]


def test_extract_sec_html_ignores_inline_xbrl_header_content():
    source = """
    <html><body>
      <ix:header><ix:hidden><ix:nonfraction name="us-gaap:Revenue">999</ix:nonfraction></ix:hidden></ix:header>
      <p>Visible filing text.</p>
    </body></html>
    """

    document = extract_sec_html(source)

    assert [block.text for block in document.blocks] == ["Visible filing text."]


def test_extract_sec_html_combines_split_sec_item_heading():
    source = """
    <html><body><div>Item 1.</div><div>Business</div><p>Company overview.</p></body></html>
    """

    document = extract_sec_html(source)

    assert document.blocks[0].text == "Item 1. Business"
    assert document.blocks[-1].section_path == ("Item 1. Business",)


def test_extract_sec_html_does_not_duplicate_table_descendants_as_narrative():
    source = """
    <html><body>
      <p>Results</p>
      <table><tr><th>Metric</th><th><p>2025</p></th><th>2024</th></tr>
      <tr><td><div>Revenue</div></td><td>10</td><td>9</td></tr>
      <tr><td>Income</td><td>9</td><td>8</td></tr></table>
      <p>After the table.</p>
    </body></html>
    """

    document = extract_sec_html(source)

    narrative = [block.text for block in document.blocks if block.kind == "text"]
    assert narrative == ["Results", "After the table."]


def test_extract_sec_html_preserves_rejected_table_as_narrative():
    source = """
    <html><body><p>Executive officers</p><table>
      <tr><th>Name</th><th>Age</th><th>Position</th></tr>
      <tr><td>Jane Doe</td><td>57</td><td>Chief Executive Officer</td></tr>
    </table></body></html>
    """

    document = extract_sec_html(source)

    assert document.tables == ()
    assert [block.text for block in document.blocks] == [
        "Executive officers",
        "Name Age Position Jane Doe 57 Chief Executive Officer",
    ]
