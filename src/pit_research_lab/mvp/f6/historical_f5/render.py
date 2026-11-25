"""Accessible static HTML for the closed historical snapshot."""

from __future__ import annotations

from html import escape

from . import contract as c
from .archive import HISTORICAL, PROFILE_BASE
from .contract import Record

STYLE = """
:root{color-scheme:light;font-family:system-ui,sans-serif;color:#172a2a;background:#f3f6f3}
*{box-sizing:border-box}
body{margin:0}
header,main,footer{max-width:72rem;margin:auto;padding:1.25rem clamp(1rem,4vw,3rem)}
header{border-bottom:1px solid #bbc9c2}
h1,h2,h3,h4{line-height:1.2}
h1{font-size:clamp(1.8rem,5vw,3rem);margin:.5rem 0}
p,li,td,th,summary,dd{line-height:1.5}
section{scroll-margin:1rem;margin-bottom:2rem}
a{color:#135357;text-underline-offset:.18em}
:focus-visible{outline:3px solid #174bd5;outline-offset:4px}
.skip{position:absolute;left:1rem;top:.5rem;transform:translateY(-200%);background:white}
.skip:focus{transform:none}
.status{display:inline-block;border:1px solid #537872;border-radius:.3rem;padding:.25rem .5rem}
nav ul{display:flex;flex-wrap:wrap;gap:.65rem 1.25rem;list-style:none;padding:0}
.table{overflow-x:auto;border:1px solid #bbc9c2;border-radius:.35rem;background:white}
table{border-collapse:collapse;width:100%}
caption{text-align:left;font-weight:700;padding:.55rem .65rem}
th,td{padding:.5rem .65rem;border-top:1px solid #d9e3de;text-align:left;vertical-align:top}
thead{background:#e8efeb}
dt{font-weight:650;margin-top:.55rem}
dd{margin:.15rem 0}
small{display:block}
code{overflow-wrap:anywhere;word-break:break-word}
details{margin:.15rem 0;min-width:9rem}
summary{cursor:pointer}
.tick{border-top:1px solid #bbc9c2;padding-top:1rem}
.tick:target{border-top:3px solid #28605b}
.stack{display:grid;gap:.75rem;grid-template-columns:repeat(auto-fit,minmax(min(100%,16rem),1fr))}
footer{border-top:1px solid #bbc9c2}
"""
RULES = {
    "BENCHMARK": "Equal-weight the qualified synthetic roster, with the fixed 50% issuer cap.",
    "A": "Select positive recorded revenue growth and apply the same issuer cap.",
    "B": "Select positive recorded OLS forecasts and apply the same issuer cap.",
}
POLICY_NAMES = {"BENCHMARK": "Benchmark", "A": "Policy A · growth", "B": "Policy B · forecast"}
COUNTS = {
    "ticks": "Weekly cutoffs",
    "valid_slots": "Valid policy slots",
    "oos_cells": "OOS forecast cells",
    "historical_bindings": "Historical bindings",
    "qualified_marks": "Qualified synthetic marks",
    "mark_sessions": "Exchange sessions in the synthetic calendar",
    "rebalance_records": "Rebalance records including mirrors",
    "valuation_records": "Valuations",
}
METRICS = {
    "net_return": "Net cumulative return",
    "linked_gross_return": "Linked pre-friction gross return",
    "max_drawdown": "Maximum daily-event drawdown",
    "weekly_sample_volatility": "Weekly sample volatility",
    "fees": "Total fees",
    "slippage": "Total slippage",
    "valid_slots": "Valid slots",
    "opportunities": "Rebalance opportunities",
    "return_count": "Weekly return intervals",
    "allocate_count": "Allocate",
    "cash_count": "Cash",
    "abstain_count": "Abstain",
}
SAFE_REASONS = {
    "UNKNOWN_EDITION": "The exact historical edition was unavailable.",
    "ARCHIVE_MISSING": "The custodian archive was missing at this check.",
    "PEER_MISSING": "The expected retained peer was missing.",
    "PAIR_INCOMPLETE": "The archived comparison was incomplete.",
    "PAIR_DEGRADED": "The archived comparison was diagnostic only.",
    "PAIR_FAILED": "The archived attempt reported a failure.",
    "EDITION_WITHHELD": "The custodian release is withheld.",
}


def _e(value: object) -> str:
    return escape(str(value), quote=True)


def _format_fraction(n: int, d: int, *, percent: bool) -> str:
    numerator = abs(n) * (1_000_000 if percent else 10_000)
    scaled, remainder = divmod(numerator, d)
    if 2 * remainder > d or (2 * remainder == d and scaled % 2):
        scaled += 1
    whole, places = divmod(scaled, 10_000)
    minus = "−" if n < 0 and scaled else ""
    return f"{minus}{whole:,}.{places:04d}" + ("%" if percent else " synthetic NTD")


def _metric(value: Record) -> str:
    if value["kind"] == "NATIVE_DECIMAL_12":
        raw = c.decimal12(value["text"])
        whole, places = raw.split(".")
        display = _format_fraction(int(whole + places), 10**12, percent=True)
        return f"<span>{_e(display)}</span><details><summary>Archived 12-place ratio</summary><code>{_e(raw)}</code></details>"
    n, d = c.fraction(value, unit=value["unit"])
    display = _format_fraction(n, d, percent=value["unit"] == "RATIO")
    exact = f"{value['numerator']}/{value['denominator']}"
    return f"<span>{_e(display)}</span><details><summary>Exact fraction</summary><code>{_e(exact)}</code></details>"


def _table(caption: str, labels: list[str], rows: list[list[str]]) -> str:
    header = "".join(f'<th scope="col">{_e(label)}</th>' for label in labels)
    body = "".join(
        '<tr><th scope="row">'
        + cells[0]
        + "</th>"
        + "".join(f"<td>{cell}</td>" for cell in cells[1:])
        + "</tr>"
        for cells in rows
    )
    return (
        f'<div class="table" tabindex="0" aria-label="{_e(caption)}"><table>'
        f"<caption>{_e(caption)}</caption><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table></div>"
    )


def _definitions(rows: list[tuple[str, str]]) -> str:
    return "<dl>" + "".join(f"<dt>{_e(key)}</dt><dd>{item}</dd>" for key, item in rows) + "</dl>"


def _overview(view: Record) -> str:
    data = view["overview"]
    metrics = [(label, _e(f"{data['coverage'][key]:,}")) for key, label in COUNTS.items()]
    overview = [
        ("Decision window (Taipei)", f"{_e(data['first_cutoff'])} to {_e(data['last_cutoff'])}"),
        ("Report terminal (Taipei)", _e(data["terminal_at"])),
        ("Synthetic issuer roster", _e(", ".join(data["issuers"]))),
        ("Method", f"<code>{_e(data['method'])}</code> · seed {_e(data['seed'])}"),
        ("Archived fit wording", f"<code>{_e(data['fit_clock_wording'])}</code>"),
        (
            "Actual fit clocks",
            _e(", ".join(f"{fit['fold']} on {fit['fit_at']}" for fit in data["actual_fits"])),
        ),
        ("Initial capital", _metric(data["initial_cash"])),
        ("Per-notional fee", _metric(data["fee_rate"])),
        ("Per-notional slippage", _metric(data["slippage_rate"])),
    ]
    return (
        '<section id="overview"><h2>Experiment overview</h2>'
        f"<p>{_e(data['question'])}</p><p>Weekly decisions use a "
        f"{_e(data['forecast_sessions'])}-session forward-return forecast. The simulation references "
        "the next session’s synthetic close and records posting one second later. "
        "Both actual fits were at 17:00 Taipei on the first test Weekly tick of their fold. "
        "The archived protocol used the wording below.</p>"
        f'<div class="stack">{_definitions(overview)}{_definitions(metrics)}</div></section>'
    )


def _comparison(view: Record) -> str:
    books = view["comparison"]
    rows = [
        [
            _e(label),
            *[(_metric(book[key]) if type(book[key]) is dict else _e(book[key])) for book in books],
        ]
        for key, label in METRICS.items()
    ]
    return (
        '<section id="comparison"><h2>Policy comparison</h2><p>Each column uses the same '
        "cutoff-qualified information. Gross links pre-friction factors. Net includes both costs. "
        "Weekly sample volatility is unannualized. Percentage and cash displays use half-even "
        "rounding to four places, with exact values available below.</p>"
        + _table(
            "Three costed policies",
            ["Measure", *[POLICY_NAMES[book["policy"]] for book in books]],
            rows,
        )
        + "</section>"
    )


def _fact(value: Record) -> str:
    if value["state"] != "KNOWN":
        return _e(value["state"] + " · " + value["reason"])
    return (
        f"{_e(value['month'])} · known, synthetic qualification"
        f"<small>Published {_e(value['publication'])}</small>"
        f"<small>Available {_e(value['available_at'])}</small>"
    )


def _signal(value: Record) -> str:
    if value["state"] == "VALUE":
        return _metric(value["metric"])
    return _e(value["state"] + " · " + value["reason"])


def _policy(policy: Record) -> str:
    label = POLICY_NAMES[policy["policy"]]
    caption = f"{label} target and recorded reasons"
    lines = [
        [_e(item["issuer"]), _metric(item["weight"]), _e(item["recorded_reason"])]
        for item in policy["weights"]
    ]
    return (
        f"<h4>{_e(label)}</h4><p>{_e(RULES[policy['policy']])}</p>"
        f"<div>Recorded disposition <strong>{_e(policy['disposition'])}</strong>. "
        f"Target cash {_metric(policy['cash_weight'])}</div>"
        + _table(caption, ["Issuer", "Target weight", "Recorded reason"], lines)
        + "<p><strong>Subsequent evaluation</strong>"
        f" · {_e(policy['event'])} · Reference {_e(policy['reference_at'])}"
        f" · Posted {_e(policy['posted_at'])}</p>"
    )


def _tick(tick: Record) -> str:
    heading = f"Tick {tick['tick']} · {tick['cutoff']}"
    lines = [
        [
            _e(issuer["issuer"]),
            _e(issuer["scope"]["state"]),
            _fact(issuer["current_revenue"]),
            _fact(issuer["preceding_revenue"]),
            _signal(issuer["growth"]),
            _signal(issuer["forecast"]),
        ]
        for issuer in tick["issuers"]
    ]
    return (
        f'<section class="tick" id="tick-{_e(tick["tick"])}" tabindex="-1">'
        f"<h3>{_e(heading)}</h3><p>Fold {_e(tick['fold'])}. "
        f"Common information <code>{_e(tick['information_ref'])}</code></p>"
        + _table(
            "Same decision inputs for all three policies",
            ["Issuer", "Scope", "Current release", "Preceding release", "Growth", "OLS forecast"],
            lines,
        )
        + "".join(_policy(policy) for policy in tick["policies"])
        + '<p><a href="#tick-index">Back to tick index</a></p></section>'
    )


def _explorer(view: Record) -> str:
    ticks = view["ticks"]
    groups = []
    for fold in ("F1", "F2"):
        items = [
            f'<li><a href="#tick-{_e(t["tick"])}">Tick {_e(t["tick"])} · {_e(t["cutoff"][:10])}</a></li>'
            for t in ticks
            if t["fold"] == fold
        ]
        groups.append(f"<h3>{_e(fold)}</h3><ul>{''.join(items)}</ul>")
    return (
        '<section id="explorer"><h2>Decision explorer</h2>'
        "<p>Forecasts are decision inputs. Subsequent events use evaluation-only marks.</p>"
        f'<nav id="tick-index" aria-label="Recorded decision ticks">{"".join(groups)}</nav>'
        + "".join(_tick(tick) for tick in ticks)
        + "</section>"
    )


def _evidence(view: Record) -> str:
    data = view["evidence"]
    labels = [
        ("Acceptance reference", _e(data["acceptance_ref"])),
        ("Historical work unit", _e(data["historical_wu"])),
        ("Original accepted revision", f"<code>{_e(data['original_revision'])}</code>"),
        ("Historical comparison class", _e(data["historical_class"])),
        ("Evidence scope", "Authored synthetic Mode S only · Non-IF03 · No App admission"),
        ("Local release identity", f"<code>{_e(view['release_id'])}</code>"),
    ]
    labels.extend(
        (label, f"<code>{_e(data[field])}</code>")
        for field, label in (
            ("f3_experiment_ref", "Original experiment"),
            ("f3_protocol_ref", "F3 protocol"),
            ("dataset_digest", "Authorized dataset"),
            ("source_fixture_sha256", "Authored source fixture"),
            ("f3_evidence_sha256", "F3 evidence"),
            ("f5_evidence_sha256", "Common F5 evidence"),
            ("archive_sha256", "Retained archive"),
            ("archive_manifest_sha256", "Archive manifest"),
            ("effective_report_sha256", "Retained effective report"),
        )
    )
    return (
        '<section id="evidence"><h2>Evidence and provenance</h2>'
        "<p>Historical execution succeeded and paired replay was verified at the original revision.</p>"
        f"<p>Current archive check completed at {_e(data['validated_at'])}.</p>"
        "<ul><li>Current native pair verification: not run.</li><li>Current research: not run.</li></ul>"
        f"<p>The recorded original revision <code>{_e(HISTORICAL)}</code> differs from the "
        f"U1 integration baseline <code>{_e(PROFILE_BASE)}</code>. "
        "This is a fixed provenance distinction. The native verifier would return "
        "<code>REPLAY_SOURCE_PROTOCOL</code> under the merged checkout if it reached that check. "
        "There is no observation of a current native verifier invocation.</p>"
        "<p>Descriptive synthetic outcomes only. The retained Run A clock has a realtime "
        "discontinuity. The export supplies no independent historical timing authentication.</p>"
        + _definitions(labels)
        + "</section>"
    )


def static_html(value: object) -> bytes:
    view = c.validate(value)
    available = view["status"] == "AVAILABLE_HISTORICAL"
    nav = ""
    if available:
        nav = (
            '<nav aria-label="Page sections"><ul><li><a href="#overview">Overview</a></li>'
            '<li><a href="#comparison">Comparison</a></li><li><a href="#explorer">Decision explorer</a></li>'
            '<li><a href="#evidence">Evidence</a></li></ul></nav>'
        )
        body = _overview(view) + _comparison(view) + _explorer(view) + _evidence(view)
    else:
        message = SAFE_REASONS.get(
            view["reason"], "The archived evidence could not be disclosed at this check."
        )
        body = (
            '<section aria-labelledby="refusal"><h2 id="refusal">Snapshot unavailable</h2>'
            f"<p>{_e(message)} <code>{_e(view['reason'])}</code></p>"
            f"<p>Archive validation {_e(view['archive_validation'])}.</p>"
            "<p>Current native pair verification: not run. Current research: not run.</p></section>"
        )
    title_status = _e(view["status"].replace("_", " ").capitalize())
    header_time = f"Archive checked {_e(view['evidence']['validated_at'])}. " if available else ""
    html = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
        "style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'\">"
        f"<title>Weekly synthetic comparison</title><style>{STYLE}</style></head><body>"
        '<a class="skip" href="#content">Skip to content</a><header><h1>Weekly synthetic comparison</h1>'
        f'<p class="status">{title_status}</p>'
        f"<p>{header_time}Exported {_e(view['observed_at'])}. Browser opening time is independent. "
        "This dated file records the export-time check only. "
        "A later withholding decision affects future exports. Saved files remain under custodian control.</p>"
        f'{nav}</header><main id="content" tabindex="-1">{body}</main>'
        f"<footer><p>Viewer build <code>{_e(view['build_sha256'])}</code></p>"
        f"<p>Snapshot <code>{_e(view['snapshot_id'])}</code></p></footer></body></html>"
    ).encode()
    c.require(len(html) <= c.MAX_HTML, "BOUNDS_EXCEEDED")
    return html
