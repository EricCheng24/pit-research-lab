"""Exact fractional self-financing book, event returns, drift and descriptive risk."""

from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from pit_research_lab.mvp.f3_l1.contracts import decimal_text, fraction_wire

from .contracts import require


@dataclass(frozen=True, slots=True)
class Book:
    cash: Fraction
    shares: tuple[tuple[str, Fraction], ...]

    @classmethod
    def initial(cls, issuers: tuple[str, ...], cash: Fraction = Fraction(1000)) -> "Book":
        return cls(cash, tuple((i, Fraction()) for i in issuers))

    def equity(self, prices: tuple[tuple[str, Fraction], ...]) -> Fraction:
        require(type(self.cash) is Fraction and self.cash >= 0, "CASH_INVARIANT")
        require(tuple(i for i, _ in self.shares) == tuple(i for i, _ in prices), "ACCOUNTING_GRID")
        require(
            all(
                type(q) is Fraction and q >= 0 and type(p) is Fraction and p > 0
                for (_, q), (_, p) in zip(self.shares, prices, strict=True)
            ),
            "ACCOUNTING_VALUES",
        )
        value = self.cash + sum(
            (q * p for (_, q), (_, p) in zip(self.shares, prices, strict=True)), Fraction()
        )
        fraction_wire(value)
        require(value > 0, "ZERO_EQUITY")
        return value


@dataclass(frozen=True, slots=True)
class Fill:
    before: Book
    after: Book
    prices: tuple[tuple[str, Fraction], ...]
    pre_equity: Fraction
    post_equity: Fraction
    traded_notional: Fraction
    fee: Fraction
    slippage: Fraction
    delta_shares: tuple[tuple[str, Fraction], ...]
    target_turnover: Fraction
    executed_turnover: Fraction
    one_way_turnover: Fraction
    pre_weights: tuple[tuple[str, Fraction], ...]
    post_weights: tuple[tuple[str, Fraction], ...]
    pre_cash_weight: Fraction
    post_cash_weight: Fraction


def rebalance(
    book: Book,
    prices: tuple[tuple[str, Fraction], ...],
    weights: tuple[tuple[str, Fraction], ...],
    fee: Fraction = Fraction(6, 10000),
    slippage: Fraction = Fraction(4, 10000),
) -> Fill:
    E = book.equity(prices)
    require(
        type(fee) is Fraction
        and type(slippage) is Fraction
        and fee >= 0
        and slippage >= 0
        and fee + slippage < 1,
        "COST_MODEL",
    )
    require(tuple(i for i, _ in weights) == tuple(i for i, _ in prices), "ACCOUNTING_GRID")
    require(
        all(type(w) is Fraction and 0 <= w <= Fraction(1, 2) for _, w in weights), "INVALID_WEIGHTS"
    )
    W = sum((w for _, w in weights), Fraction())
    require(W <= 1, "INVALID_WEIGHTS")
    x = tuple(q * p for (_, q), (_, p) in zip(book.shares, prices, strict=True))
    ws = tuple(w for _, w in weights)
    points = sorted(
        {Fraction(), E, *(v / w for v, w in zip(x, ws, strict=True) if w and 0 <= v / w <= E)}
    )
    V = None
    c = fee + slippage
    for low, high in zip(points, points[1:], strict=False):
        mid = (low + high) / 2
        signs = tuple(1 if w * mid >= v else -1 for w, v in zip(ws, x, strict=True))
        a = sum((s * w for s, w in zip(signs, ws, strict=True)), Fraction())
        b = sum((-s * v for s, v in zip(signs, x, strict=True)), Fraction())
        candidate = (E - c * b) / (1 + c * a)
        if low <= candidate <= high:
            V = candidate
            break
    require(V is not None, "SELF_FINANCING_ROOT")
    assert V is not None
    notional = sum((abs(w * V - v) for w, v in zip(ws, x, strict=True)), Fraction())
    require(V == E - c * notional, "SELF_FINANCING_ROOT")
    shares = tuple((i, w * V / p) for (i, w), (_, p) in zip(weights, prices, strict=True))
    delta = tuple((i, new - old) for (i, new), (_, old) in zip(shares, book.shares, strict=True))
    cash = (
        book.cash
        - sum((dq * p for (_, dq), (_, p) in zip(delta, prices, strict=True)), Fraction())
        - c * notional
    )
    after = Book(cash, shares)
    require(
        cash == V * (1 - W) and after.equity(prices) == V and cash >= 0, "SELF_FINANCING_INVARIANT"
    )
    pre = tuple((i, v / E) for (i, _), v in zip(prices, x, strict=True))
    turnover = (
        sum((abs(w - v / E) for w, v in zip(ws, x, strict=True)), Fraction())
        + abs((1 - W) - book.cash / E)
    ) / 2
    for number in (V, notional, cash, turnover, *(q for _, q in shares)):
        fraction_wire(number)
    return Fill(
        book,
        after,
        prices,
        E,
        V,
        notional,
        fee * notional,
        slippage * notional,
        delta,
        turnover,
        notional / E,
        notional / (2 * E),
        pre,
        weights,
        book.cash / E,
        1 - W,
    )


def metrics(
    equities: tuple[Fraction, ...], costs: tuple[Fraction, ...], weekly: tuple[Fraction, ...]
) -> dict[str, Any]:
    require(
        bool(equities)
        and len(equities) == len(costs)
        and all(type(e) is Fraction and e > 0 for e in equities)
        and all(type(c) is Fraction and c >= 0 for c in costs)
        and costs[0] == 0,
        "METRIC_EVENTS",
    )
    peak, drawdown, gross = equities[0], Fraction(), Fraction(1)
    for j, E in enumerate(equities):
        peak = max(peak, E)
        drawdown = max(drawdown, 1 - E / peak)
        if j:
            gross *= (E + costs[j]) / equities[j - 1]
    returns = tuple(b / a - 1 for a, b in zip(weekly, weekly[1:], strict=False))
    mean = sum(returns, Fraction()) / len(returns) if returns else None
    variance = (
        sum(((r - mean) ** 2 for r in returns), Fraction()) / (len(returns) - 1)
        if len(returns) >= 2 and mean is not None
        else None
    )
    return {
        "net_return": equities[-1] / equities[0] - 1,
        "linked_pre_friction_gross_return": gross - 1,
        "maximum_daily_event_drawdown": drawdown,
        "weekly_returns": returns,
        "weekly_return_count": len(returns),
        "weekly_mean": mean,
        "weekly_sample_variance": variance,
        "weekly_volatility_display": decimal_text(variance, sqrt=True)
        if variance is not None
        else "NOT_COMPUTABLE",
        "annualization": "NOT_PERFORMED",
        "iid_inference": "NOT_PERFORMED",
    }
