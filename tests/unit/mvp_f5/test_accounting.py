"""Exact Oracle 1 and independent self-financing invariants; no empirical returns."""

from fractions import Fraction as Q
from itertools import product

import pytest

from pit_research_lab.mvp.f5.accounting import Book, metrics, rebalance
from pit_research_lab.mvp.f5.contracts import F5Error


def test_original_two_week_hand_ledger_exact_and_cost_zero_mirror():
    book = Book.initial(("A", "B"), Q(1010))
    first = rebalance(
        book, (("A", Q(100)), ("B", Q(50))), (("A", Q(1, 2)), ("B", Q(1, 2))), Q(3, 500), Q(1, 250)
    )
    assert first.post_equity == 1000 and first.after == Book(Q(), (("A", Q(5)), ("B", Q(10))))
    assert (first.fee, first.slippage, first.executed_turnover, first.target_turnover) == (
        Q(6),
        Q(4),
        Q(100, 101),
        Q(1),
    )
    friday = first.after.equity((("A", Q(110)), ("B", Q(55))))
    second = rebalance(
        first.after,
        (("A", Q(100)), ("B", Q(99, 2))),
        (("A", Q()), ("B", Q(1, 2))),
        Q(3, 500),
        Q(1, 250),
    )
    assert second.pre_equity == 995 and second.post_equity == 990
    assert second.after == Book(Q(495), (("A", Q()), ("B", Q(10))))
    assert (second.traded_notional, second.fee, second.slippage) == (Q(500), Q(3), Q(2))
    assert second.executed_turnover == second.target_turnover == Q(100, 199)
    assert second.pre_weights == (("A", Q(100, 199)), ("B", Q(99, 199)))
    end = second.after.equity((("A", Q(90)), ("B", Q(891, 20))))
    assert end == Q(1881, 2)
    # Include actual old-book and post-cost events, with all flat daily marks.
    eq = (
        Q(1010),
        Q(1010),
        Q(1010),
        Q(1000),
        *(Q(1100) for _ in range(4)),
        Q(995),
        Q(990),
        *(end for _ in range(4)),
    )
    costs = (Q(), Q(), Q(), Q(10), *(Q() for _ in range(5)), Q(5), *(Q() for _ in range(4)))
    result = metrics(eq, costs, (Q(1010), friday, end))
    assert result["net_return"] == Q(-139, 2020)
    assert result["linked_pre_friction_gross_return"] == Q(-219, 4000)
    assert result["maximum_daily_event_drawdown"] == Q(29, 200)
    assert result["weekly_returns"] == (Q(9, 101), Q(-29, 200))
    assert result["weekly_sample_variance"] == Q(4729, 20200) ** 2 / 2
    mirror1 = rebalance(book, first.prices, first.post_weights, Q(), Q())
    mirror2 = rebalance(mirror1.after, second.prices, second.post_weights, Q(), Q())
    mirror_end = mirror2.after.equity((("A", Q(90)), ("B", Q(891, 20))))
    assert mirror1.after.shares == (("A", Q(101, 20)), ("B", Q(101, 10)))
    assert mirror2.after.cash == Q(20099, 40)
    assert mirror_end == Q(381881, 400)  # 954.7025; not E_net + fees.


def test_self_financing_piecewise_roots_drift_cash_and_no_double_charge():
    prices = (("A", Q(123, 10)), ("B", Q(87, 7)))
    book = Book(Q(87), (("A", Q(3)), ("B", Q(5))))
    for a, b in product((Q(), Q(1, 5), Q(1, 2)), repeat=2):
        fill = rebalance(book, prices, (("A", a), ("B", b)))
        assert fill.after.equity(prices) == fill.pre_equity - fill.fee - fill.slippage
        assert fill.after.cash == fill.post_equity * (1 - a - b) >= 0
        assert fill.fee == Q(6, 10000) * fill.traded_notional
        assert fill.slippage == Q(4, 10000) * fill.traded_notional
        assert fill.executed_turnover * fill.pre_equity == fill.traded_notional
        assert fill.after.shares[0][1] * prices[0][1] == a * fill.post_equity
    # No cost on already-held cash or unchanged shares.
    cash = Book.initial(("A", "B"))
    fill = rebalance(cash, prices, (("A", Q()), ("B", Q())))
    assert fill.after == cash and fill.traded_notional == fill.fee == fill.slippage == 0
    sold = rebalance(book, prices, (("A", Q()), ("B", Q())))
    assert sold.after.cash == sold.post_equity and all(q == 0 for _, q in sold.after.shares)


def test_old_holdings_own_fill_day_movement_and_future_marks_do_not_resize():
    book = Book(Q(500), (("A", Q(5)), ("B", Q())))
    prices = (("A", Q(90)), ("B", Q(40)))
    fill = rebalance(book, prices, (("A", Q()), ("B", Q(1, 2))))
    assert fill.pre_equity == 950  # old A suffered 100 -> 90 before the fill.
    before = fill.after
    future = (("A", Q(1000000)), ("B", Q(20)))
    after = before.equity(future)
    assert fill.after == before and after < fill.post_equity
    assert fill.fee + fill.slippage == Q(1, 1000) * fill.traded_notional


@pytest.mark.parametrize("mutation", ["negative", "overcap", "float", "fee", "price", "grid"])
def test_illegal_weights_costs_prices_refused(mutation):
    book = Book.initial(("A", "B"))
    prices, weights, fee = (("A", Q(1)), ("B", Q(2))), (("A", Q(1, 2)), ("B", Q(1, 2))), Q()
    if mutation == "negative":
        weights = (("A", Q(-1)), ("B", Q()))
    if mutation == "overcap":
        weights = (("A", Q(1)), ("B", Q()))
    if mutation == "float":
        weights = (("A", 0.5), ("B", Q(1, 2)))
    if mutation == "fee":
        fee = Q(1)
    if mutation == "price":
        prices = (("A", Q()), ("B", Q(1)))
    if mutation == "grid":
        weights = (("OTHER", Q()), ("B", Q()))
    with pytest.raises(F5Error):
        rebalance(book, prices, weights, fee, Q())
