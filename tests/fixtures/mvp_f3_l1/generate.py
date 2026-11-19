"""Author v1 inputs only; never imports the experiment or inspects its outputs."""

import calendar
import hashlib
import json
import random
from datetime import date, timedelta
from pathlib import Path


def generate():
    revenue_rng, price_rng = random.Random(17), random.Random(17001)
    issuers = [f"SYN-L1-{i}" for i in range(1, 6)]
    days = []
    day = date(2024, 1, 1)
    while day <= date(2026, 2, 28):
        closed = day.weekday() >= 5 or date(2024, 10, 7) <= day <= date(2024, 10, 13)
        closed = closed or day in {date(2024, 4, 4), date(2025, 1, 1)}
        days.append(
            {
                "date": str(day),
                "status": "CLOSED" if closed else "SESSION",
                "close": None
                if closed
                else str(day)
                + ("T11:30:00+08:00" if day == date(2024, 12, 31) else "T13:30:00+08:00"),
            }
        )
        day += timedelta(days=1)
    weekly = {}
    for row in days:
        if row["status"] == "SESSION" and row["date"] >= "2024-03-04":
            weekly[date.fromisoformat(row["date"]).isocalendar()[:2]] = row["date"]
    cutoffs = [d + "T18:00:00+08:00" for d in list(weekly.values())[:96]]
    revenue = []
    for issuer in issuers:
        for month_index in range(26):
            year, month = 2024 + month_index // 12, month_index % 12 + 1
            next_year, next_month = year + month // 12, month % 12 + 1
            publication = f"{next_year}-{next_month:02}-10T12:00:00+08:00"
            ref = f"{issuer}-REV-{year}-{month:02}"
            revenue.append(
                {
                    "id": ref,
                    "issuer": issuer,
                    "month": f"{year}-{month:02}",
                    "period_end": f"{year}-{month:02}-{calendar.monthrange(year, month)[1]}",
                    "publication": publication,
                    "available_at": publication.replace("12:00", "12:01"),
                    "effective_at": f"{year}-{month:02}-01T00:00:00+08:00",
                    "state": "UNKNOWN" if issuer == issuers[0] and month_index == 3 else "KNOWN",
                    "amount": None
                    if issuer == issuers[0] and month_index == 3
                    else revenue_rng.randint(800, 1200),
                    "unit": "NTD_thousands",
                    "basis": "consolidated-v1",
                    "supersedes": None,
                }
            )
    original = next(r for r in revenue if r["issuer"] == issuers[1] and r["month"] == "2024-04")
    revenue.append(
        {
            **original,
            "id": original["id"] + "-R1",
            "supersedes": original["id"],
            "publication": "2024-05-17T18:00:00+08:00",
            "available_at": "2024-05-17T18:00:00+08:00",
            "amount": 1023,
        }
    )
    prices = []
    levels = {issuer: 100000 for issuer in issuers}
    for row in days:
        if row["status"] != "SESSION":
            continue
        common = price_rng.randint(-90, 90)
        for issuer in issuers:
            levels[issuer] += common + price_rng.randint(-200, 200)
            prices.append(
                {
                    "id": f"{issuer}-CLOSE-{row['date']}",
                    "issuer": issuer,
                    "session": row["date"],
                    "value": levels[issuer],
                    "available_at": row["close"].replace(":00+", ":01+"),
                    "unit": "NTD_price_ticks_1e4",
                    "basis": "unadjusted-synthetic-v1",
                }
            )
    return {
        "schema": "F2_L1_AUTHORED_PANEL_V1",
        "generator": "independent-streams-v1",
        "seed": 17,
        "price_seed": 17001,
        "issuers": issuers,
        "calendar_id": "SYN-L1-CALENDAR-V1",
        "calendar": days,
        "cutoffs": cutoffs,
        "revenues": revenue,
        "prices": prices,
        "outcome_release_delay_sessions": 1,
        "limitations": [
            "AUTHORED_SYNTHETIC_ONLY",
            "NOT_SOURCE_AUTHENTICATION",
            "NO_IF03_ISSUANCE",
            "COMMON_PRICE_SHOCK",
            "OVERLAPPING_OUTCOMES",
        ],
    }


if __name__ == "__main__":
    root = Path(__file__).parent
    path = root / "revenue_growth_panel_v0_1.json"
    if path.exists():
        raise SystemExit("Refuse overwrite: new structural editions require a new filename/version")
    raw = json.dumps(generate(), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    path.write_bytes(raw)
    (root / "manifest_v0_1.json").write_text(
        json.dumps(
            {
                "schema": "F2_L1_SOURCE_MANIFEST_V1",
                "file": path.name,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "byte_length": len(raw),
                "generator": "independent-streams-v1",
                "seed": 17,
                "price_seed": 17001,
                "qualification": "NOT_IMPLIED_BY_MANIFEST",
                "non_if03": True,
            },
            indent=2,
        )
        + "\n"
    )
