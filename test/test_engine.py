# Test type: Unit and integration (business-rule level)
# Validation: Parsing, q/p/k temporal rules, return computation, and validator duplicate handling
# Command: pytest -q

from app.core.engine import (
    build_period_payload,
    build_transactions,
    calculate_returns,
    filter_transactions,
    validate_transactions,
)


def _example_expenses():
    return [
        {"timestamp": "2023-10-12 20:15:00", "amount": 250},
        {"timestamp": "2023-02-28 15:49:00", "amount": 375},
        {"timestamp": "2023-07-01 21:59:00", "amount": 620},
        {"timestamp": "2023-12-17 08:09:00", "amount": 480},
    ]


def _example_periods():
    q = [{"fixed": 0, "start": "2023-07-01 00:00", "end": "2023-07-31 23:59"}]
    p = [{"extra": 25, "start": "2023-10-01 08:00", "end": "2023-12-31 19:59"}]
    k = [
        {"start": "2023-03-01 00:00", "end": "2023-11-30 23:59"},
        {"start": "2023-01-01 00:00", "end": "2023-12-31 23:59"},
    ]
    return q, p, k


def test_challenge_example_temporal_amounts_and_index_returns():
    built = build_transactions(_example_expenses())
    q, p, k = _example_periods()
    q_periods, p_periods, k_periods = build_period_payload(q, p, k)

    result = calculate_returns(
        instrument="index",
        age=29,
        wage=50000,
        inflation=0.055,
        transactions=built["transactions"],
        q_periods=q_periods,
        p_periods=p_periods,
        k_periods=k_periods,
    )

    assert result["transactionsTotalAmount"] == 1725.0
    assert result["transactionsTotalCeiling"] == 1900.0
    assert result["savingsByDates"][0]["amount"] == 75.0
    assert result["savingsByDates"][1]["amount"] == 145.0
    assert result["savingsByDates"][1]["profits"] == 1684.51


def test_q_latest_start_wins_and_p_overlaps_add():
    transactions = build_transactions(
        [{"timestamp": "2023-06-15 10:00:00", "amount": 120}]
    )["transactions"]

    q = [
        {"fixed": 10, "start": "2023-01-01 00:00", "end": "2023-12-31 23:59"},
        {"fixed": 40, "start": "2023-06-01 00:00", "end": "2023-06-30 23:59"},
    ]
    p = [
        {"extra": 5, "start": "2023-06-10 00:00", "end": "2023-06-20 23:59"},
        {"extra": 7, "start": "2023-06-12 00:00", "end": "2023-06-18 23:59"},
    ]
    k = [{"start": "2023-01-01 00:00", "end": "2023-12-31 23:59"}]
    q_periods, p_periods, k_periods = build_period_payload(q, p, k)

    filtered = filter_transactions(transactions, q_periods, p_periods, k_periods)

    assert len(filtered["valid"]) == 1
    assert filtered["valid"][0]["remanent"] == 52.0
    assert filtered["valid"][0]["inKPeriod"] is True


def test_validator_flags_duplicates():
    transactions = build_transactions(
        [
            {"timestamp": "2023-01-01 10:00:00", "amount": 151},
            {"timestamp": "2023-01-01 10:00:00", "amount": 299},
        ]
    )["transactions"]
    result = validate_transactions(wage=50000, transactions=transactions)

    assert len(result["valid"]) == 1
    assert len(result["duplicates"]) == 1
