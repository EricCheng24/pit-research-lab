"""Static browser-document guarantees on independent synthetic data."""

from __future__ import annotations

from html.parser import HTMLParser

import pytest
from test_historical_f5_projection import (
    ATTEMPT,
    BUILD,
    OBSERVED,
    STAMP,
    synthetic_history,
    synthetic_view,
)

from pit_research_lab.mvp.f6.historical_f5 import contract, projection, render


class Structure(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.nodes: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.nodes.append((tag, dict(attrs)))


def test_H03_H04_H08_all_tick_anchors_are_static_and_self_contained() -> None:
    page = render.static_html(synthetic_view()).decode()
    markup = Structure()
    markup.feed(page)
    ids = [a["id"] for _, a in markup.nodes if "id" in a]
    assert len(ids) == len(set(ids))
    links = [a["href"] for tag, a in markup.nodes if tag == "a"]
    assert all(href and href.startswith("#") and href[1:] in ids for href in links)
    assert {x for x in ids if x and x.startswith("tick-")} == {
        "tick-index",
        *(f"tick-{n}" for n in range(48, 96)),
    }
    assert sum(href == "#tick-index" for href in links) == 48
    assert sum(tag == "caption" for tag, _ in markup.nodes) == 193
    assert all(
        tag not in {"script", "iframe", "form", "object", "img", "link"} for tag, _ in markup.nodes
    )
    assert not any(k.startswith("on") or k == "src" for _, attrs in markup.nodes for k in attrs)
    assert "default-src 'none'" in page
    for literal in (
        "Historical execution succeeded and paired replay was verified at the original revision.",
        "Current native pair verification: not run.",
        "Current research: not run.",
        "This is a fixed provenance distinction.",
        "REPLAY_SOURCE_PROTOCOL",
        "a later withholding decision affects future exports",
        "Subsequent evaluation",
        "Archived 12-place ratio",
        "Exact fraction",
        "−2.7027%",
    ):
        assert literal.lower() in page.lower()
    assert "private-not-a-view-field" not in page
    assert "529083410" not in page


@pytest.mark.parametrize(
    ("n", "d", "percent", "expected"),
    [
        (1, 20_000, False, "0.0000 synthetic NTD"),
        (-3, 20_000, False, "−0.0002 synthetic NTD"),
        (1, 2_000_000, True, "0.0000%"),
        (3, 2_000_000, True, "0.0002%"),
        (-3, 10, True, "−30.0000%"),
    ],
)
def test_H02_half_even_sign_and_units(n: int, d: int, percent: bool, expected: str) -> None:
    assert render._format_fraction(n, d, percent=percent) == expected


def test_H03_exact_long_forecast_remains_available() -> None:
    selected = synthetic_history()
    source = selected.observations[48]["issuers"][0]["forecast"]
    source["value"] = {"numerator": "1" * 4096, "denominator": "2"}
    result = projection.historical(selected, BUILD, ATTEMPT, STAMP, OBSERVED)
    html = render.static_html(result).decode()
    assert ("1" * 4096 + "/2") in html and "overflow-wrap:anywhere" in html
    assert len(html.encode()) <= contract.MAX_HTML


def test_H08_unknown_text_and_injection_are_refused_or_escaped() -> None:
    snapshot = synthetic_view()
    bad = '<script>alert("hidden")</script>'
    snapshot["evidence"]["acceptance_ref"] = bad
    with pytest.raises(contract.Refusal):
        render.static_html(snapshot)
    assert render._e(bad) == "&lt;script&gt;alert(&quot;hidden&quot;)&lt;/script&gt;"


def test_H06_refusal_page_cannot_suggest_positive_historical_release() -> None:
    result = projection.refusal("ARCHIVE_PIN", "FAILED", BUILD, ATTEMPT, OBSERVED)
    message = render.static_html(result).decode()
    assert "ARCHIVE_PIN" in message and 'id="refusal"' in message
    assert "Historical execution succeeded" not in message
    assert 'id="comparison"' not in message
