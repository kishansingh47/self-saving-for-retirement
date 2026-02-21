# Test type: Unit (core engine rules and edge handling)
# Validation: q/p bounds, returns valid-subset behavior, all-invalid returns failure, and q tie-break precedence
# Command: pytest -q

import pytest

from app.core.engine import (
    build_period_payload,
    calculate_returns,
    filter_transactions,
)


def test_build_period_payload_rejects_q_fixed_upper_bound():
    with pytest.raises(ValueError, match="q.fixed must be < 500000"):
        build_period_payload(
            q=[{"fixed": 500000, "start": "2023-01-01 00:00:00", "end": "2023-01-31 23:59:59"}],
            p=[],
            k=[],
        )


def test_build_period_payload_rejects_p_extra_upper_bound():
    with pytest.raises(ValueError, match="p.extra must be < 500000"):
        build_period_payload(
            q=[],
            p=[{"extra": 500000, "start": "2023-01-01 00:00:00", "end": "2023-01-31 23:59:59"}],
            k=[],
        )


def test_calculate_returns_uses_valid_subset_only():
    q_periods, p_periods, k_periods = build_period_payload(
        q=[],
        p=[],
        k=[{"start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:59"}],
    )

    result = calculate_returns(
        instrument="nps",
        age=29,
        wage=50000,
        inflation=5.5,
        transactions=[
            {"date": "2023-02-28 15:49:20", "amount": 375},
            {"date": "2023-10-12 20:15:30", "amount": 250},
            {"date": "2023-10-12 20:15:30", "amount": 300},  # duplicate timestamp -> ignored
            {"date": "2023-12-17 08:09:45", "amount": -10},  # invalid -> ignored
        ],
        q_periods=q_periods,
        p_periods=p_periods,
        k_periods=k_periods,
    )

    assert result["transactionsTotalAmount"] == 625.0
    assert result["transactionsTotalCeiling"] == 700.0
    assert len(result["savingsByDates"]) == 1
    assert result["savingsByDates"][0]["amount"] == 75.0
    assert result["savingsByDates"][0]["profits"] == 44.94
    assert result["savingsByDates"][0]["taxBenefit"] == 0.0


def test_calculate_returns_raises_when_no_valid_transactions():
    q_periods, p_periods, k_periods = build_period_payload(
        q=[],
        p=[],
        k=[{"start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:59"}],
    )

    with pytest.raises(ValueError, match="No valid transactions available for returns calculation"):
        calculate_returns(
            instrument="nps",
            age=29,
            wage=50000,
            inflation=5.5,
            transactions=[
                {"date": "2023-12-17 08:09:45", "amount": -10},
                {"date": "2023-12-17 08:09:45", "amount": -20},
            ],
            q_periods=q_periods,
            p_periods=p_periods,
            k_periods=k_periods,
        )


def test_filter_q_tie_break_prefers_first_period_when_same_start():
    q_periods, p_periods, k_periods = build_period_payload(
        q=[
            {"fixed": 10, "start": "2023-06-01 00:00:00", "end": "2023-06-30 23:59:59"},
            {"fixed": 25, "start": "2023-06-01 00:00:00", "end": "2023-06-30 23:59:59"},
        ],
        p=[],
        k=[{"start": "2023-01-01 00:00:00", "end": "2023-12-31 23:59:59"}],
    )

    result = filter_transactions(
        transactions=[{"date": "2023-06-15 10:00:00", "amount": 120}],
        q_periods=q_periods,
        p_periods=p_periods,
        k_periods=k_periods,
    )

    assert len(result["valid"]) == 1
    assert result["valid"][0]["remanent"] == 10.0
