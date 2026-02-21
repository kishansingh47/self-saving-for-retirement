from __future__ import annotations

import heapq
import logging
import math
from bisect import bisect_left, bisect_right

from app.core.finance import (
    INDEX_RATE,
    NPS_RATE,
    compute_real_return,
    money,
    next_multiple_of_100,
    nps_tax_benefit,
    remanent_from_amount,
    years_to_investment_horizon,
)
from app.core.time_utils import parse_timestamp_to_epoch

logger = logging.getLogger(__name__)


def _to_float(value: object, field_name: str) -> float:
    if value is None:
        raise ValueError(f"Missing field: {field_name}")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Field '{field_name}' must be numeric.") from exc


def _canonical_transaction(
    transaction: dict,
    *,
    enforce_amount_limit: bool = True,
    require_ceiling_and_remanent: bool = False,
) -> dict:
    timestamp_raw = transaction.get("date") or transaction.get("timestamp")
    if timestamp_raw is None:
        raise ValueError("Transaction must include 'date' or 'timestamp'.")

    normalized_timestamp, epoch = parse_timestamp_to_epoch(str(timestamp_raw))
    amount = _to_float(transaction.get("amount"), "amount")
    if amount < 0:
        raise ValueError("Amount cannot be negative.")
    if enforce_amount_limit and amount >= 500000:
        raise ValueError("Amount must be < 500000 as per challenge constraints.")

    if require_ceiling_and_remanent:
        ceiling = _to_float(transaction.get("ceiling"), "ceiling")
        remanent = _to_float(transaction.get("remanent"), "remanent")
    else:
        ceiling = (
            _to_float(transaction.get("ceiling"), "ceiling")
            if transaction.get("ceiling") is not None
            else next_multiple_of_100(amount)
        )
        remanent = (
            _to_float(transaction.get("remanent"), "remanent")
            if transaction.get("remanent") is not None
            else remanent_from_amount(amount)
        )

    if ceiling < amount:
        raise ValueError("Ceiling cannot be lower than amount.")
    if remanent < 0:
        raise ValueError("Remanent cannot be negative.")

    return {
        "date": normalized_timestamp,
        "timestamp": normalized_timestamp,
        "epoch": epoch,
        "amount": money(amount),
        "ceiling": money(ceiling),
        "remanent": money(remanent),
    }


def _transaction_output(transaction: dict, *, include_adjusted_remanent: bool = True) -> dict:
    payload = {
        "date": transaction["date"],
        "amount": money(transaction["amount"]),
        "ceiling": money(transaction["ceiling"]),
        "remanent": money(transaction["remanent"]),
    }
    if include_adjusted_remanent:
        payload["adjustedRemanent"] = (
            money(transaction["adjusted_remanent"])
            if "adjusted_remanent" in transaction
            else None
        )
    return payload


def _invalid_output(
    transaction: dict,
    message: str,
    *,
    include_adjusted_remanent: bool = True,
) -> dict:
    payload = {
        "date": transaction.get("date") or transaction.get("timestamp") or "",
        "amount": money(transaction.get("amount", 0.0)),
        "ceiling": money(transaction.get("ceiling", 0.0)),
        "remanent": money(transaction.get("remanent", 0.0)),
        "message": message,
    }
    if include_adjusted_remanent:
        payload["adjustedRemanent"] = (
            money(transaction["adjusted_remanent"])
            if "adjusted_remanent" in transaction
            else None
        )
    return payload


def _filter_invalid_output(transaction: dict, message: str) -> dict:
    return {
        "date": transaction.get("date") or transaction.get("timestamp") or "",
        "amount": money(transaction.get("amount", 0.0)),
        "message": message,
    }


def _prepare_returns_transactions(transactions: list[dict]) -> tuple[list[dict], int, int]:
    canonical_transactions: list[dict] = []
    seen_timestamps: set[str] = set()
    invalid_count = 0
    duplicate_count = 0

    for raw in transactions:
        try:
            normalized_input = {
                "date": raw.get("date"),
                "timestamp": raw.get("timestamp"),
                "amount": raw.get("amount"),
            }
            tx = _canonical_transaction(
                normalized_input,
                enforce_amount_limit=True,
                require_ceiling_and_remanent=False,
            )
        except ValueError:
            invalid_count += 1
            continue
        if tx["date"] in seen_timestamps:
            duplicate_count += 1
            continue
        seen_timestamps.add(tx["date"])
        canonical_transactions.append(tx)

    return canonical_transactions, invalid_count, duplicate_count


def _normalize_inflation_rate(inflation: float) -> float:
    if inflation < 0:
        raise ValueError("Inflation cannot be negative.")
    return inflation / 100.0 if inflation > 1.0 else inflation


def _build_periods(periods: list[dict], kind: str) -> list[dict]:
    built: list[dict] = []
    for index, period in enumerate(periods):
        start_raw = period.get("start")
        end_raw = period.get("end")
        if start_raw is None or end_raw is None:
            raise ValueError(f"{kind}[{index}] must include start and end.")

        start_timestamp, start_epoch = parse_timestamp_to_epoch(str(start_raw))
        end_timestamp, end_epoch = parse_timestamp_to_epoch(str(end_raw))
        if start_epoch > end_epoch:
            raise ValueError(f"{kind}[{index}] start must be <= end.")
        if kind == "k" and int(start_timestamp[0:4]) != int(end_timestamp[0:4]):
            raise ValueError(f"{kind}[{index}] cannot span multiple years.")

        built_period = {
            "start": start_timestamp,
            "end": end_timestamp,
            "start_epoch": start_epoch,
            "end_epoch": end_epoch,
            "index": index,
        }

        if kind == "q":
            fixed = _to_float(period.get("fixed"), "fixed")
            if fixed < 0:
                raise ValueError("q.fixed cannot be negative.")
            if fixed >= 500000:
                raise ValueError("q.fixed must be < 500000 as per challenge constraints.")
            built_period["value"] = money(fixed)
        elif kind == "p":
            extra = _to_float(period.get("extra"), "extra")
            if extra < 0:
                raise ValueError("p.extra cannot be negative.")
            if extra >= 500000:
                raise ValueError("p.extra must be < 500000 as per challenge constraints.")
            built_period["value"] = money(extra)

        built.append(built_period)
    return built


def build_transactions(expenses: list[dict]) -> dict:
    transactions: list[dict] = []
    for expense in expenses:
        timestamp_raw = expense.get("timestamp") or expense.get("date")
        if timestamp_raw is None:
            raise ValueError("Each expense must include a timestamp.")
        normalized_timestamp, epoch = parse_timestamp_to_epoch(str(timestamp_raw))
        amount = _to_float(expense.get("amount"), "amount")
        if amount < 0:
            raise ValueError("Expense amount cannot be negative.")
        if amount >= 500000:
            raise ValueError("Expense amount must be < 500000 as per constraints.")
        ceiling = next_multiple_of_100(amount)
        remanent = money(ceiling - amount)
        transactions.append(
            {
                "date": normalized_timestamp,
                "timestamp": normalized_timestamp,
                "epoch": epoch,
                "amount": money(amount),
                "ceiling": money(ceiling),
                "remanent": remanent,
            }
        )

    return {
        "transactions": [_transaction_output(tx) for tx in transactions],
        "transactionsTotalAmount": money(sum(tx["amount"] for tx in transactions)),
        "transactionsTotalCeiling": money(sum(tx["ceiling"] for tx in transactions)),
        "transactionsTotalRemanent": money(sum(tx["remanent"] for tx in transactions)),
    }


def validate_transactions(
    wage: float, transactions: list[dict], max_investment: float | None = None
) -> dict:
    if wage < 0:
        raise ValueError("Wage cannot be negative.")
    limit = money(max_investment if max_investment is not None else wage * 12)
    if limit < 0:
        raise ValueError("Maximum investment cannot be negative.")

    valid_candidates: list[dict] = []
    invalid: list[dict] = []
    duplicates: list[dict] = []
    seen_timestamps: set[str] = set()

    for raw in transactions:
        try:
            tx = _canonical_transaction(
                raw, enforce_amount_limit=True, require_ceiling_and_remanent=True
            )
        except ValueError as exc:
            invalid.append(
                _invalid_output(raw, str(exc), include_adjusted_remanent=False)
            )
            continue

        if tx["date"] in seen_timestamps:
            duplicates.append(
                _invalid_output(
                    tx,
                    "Duplicate transaction timestamp.",
                    include_adjusted_remanent=False,
                )
            )
            continue
        seen_timestamps.add(tx["date"])

        expected_ceiling = next_multiple_of_100(tx["amount"])
        expected_remanent = money(expected_ceiling - tx["amount"])
        if abs(tx["ceiling"] - expected_ceiling) > 0.01:
            invalid.append(
                _invalid_output(
                    tx,
                    "Invalid ceiling value for the amount. Expected next multiple of 100.",
                    include_adjusted_remanent=False,
                )
            )
            continue
        if abs(tx["remanent"] - expected_remanent) > 0.01:
            invalid.append(
                _invalid_output(
                    tx,
                    "Invalid remanent value. Expected ceiling - amount.",
                    include_adjusted_remanent=False,
                )
            )
            continue
        if tx["remanent"] > 500000:
            invalid.append(
                _invalid_output(
                    tx,
                    "Remanent exceeds challenge constraints (< 500000 required).",
                    include_adjusted_remanent=False,
                )
            )
            continue

        valid_candidates.append(tx)

    running_investment = 0.0
    valid: list[dict] = []
    for tx in valid_candidates:
        if running_investment + tx["remanent"] > limit + 1e-9:
            invalid.append(
                _invalid_output(
                    tx,
                    "Cumulative remanent exceeds maximum allowed investment.",
                    include_adjusted_remanent=False,
                )
            )
            continue
        running_investment += tx["remanent"]
        valid.append(tx)

    return {
        "valid": [
            _transaction_output(tx, include_adjusted_remanent=False) for tx in valid
        ],
        "invalid": invalid,
        "duplicates": duplicates,
    }


def _apply_temporal_rules(
    transactions: list[dict],
    q_periods: list[dict],
    p_periods: list[dict],
    *,
    ordered_indices: list[int] | None = None,
) -> list[dict]:
    if not transactions:
        return []

    if ordered_indices is None:
        ordered_indices = sorted(
            range(len(transactions)), key=lambda i: (transactions[i]["epoch"], i)
        )
    ordered_times = [transactions[index]["epoch"] for index in ordered_indices]
    q_strategy = _choose_q_strategy(ordered_times, q_periods)

    if q_strategy == "dsu":
        q_overrides_sorted = _q_overrides_dsu(ordered_times, q_periods)
    else:
        q_overrides_sorted = _q_overrides_heap(ordered_times, q_periods)

    p_start_events = sorted((p["start_epoch"], p["value"]) for p in p_periods)
    p_end_events = sorted((p["end_epoch"] + 1, p["value"]) for p in p_periods)

    p_start_pointer = 0
    p_end_pointer = 0
    running_extra = 0.0

    for sorted_position, tx_index in enumerate(ordered_indices):
        ts = ordered_times[sorted_position]
        while (
            p_start_pointer < len(p_start_events)
            and p_start_events[p_start_pointer][0] <= ts
        ):
            running_extra += p_start_events[p_start_pointer][1]
            p_start_pointer += 1

        while p_end_pointer < len(p_end_events) and p_end_events[p_end_pointer][0] <= ts:
            running_extra -= p_end_events[p_end_pointer][1]
            p_end_pointer += 1

        base_override = q_overrides_sorted[sorted_position]
        base_remanent = (
            base_override
            if base_override is not None
            else transactions[tx_index]["remanent"]
        )
        transactions[tx_index]["adjusted_remanent"] = money(base_remanent + running_extra)
    return transactions


def _choose_q_strategy(ordered_times: list[int], q_periods: list[dict]) -> str:
    q_count = len(q_periods)
    tx_count = len(ordered_times)
    if q_count == 0 or tx_count == 0:
        return "heap"

    if q_count < 2048:
        return "heap"

    sample_size = min(q_count, 4096)
    unique_bounds = set()
    for i in range(sample_size):
        period = q_periods[i]
        unique_bounds.add((period["start_epoch"], period["end_epoch"]))
    duplicate_ratio = 1.0 - (len(unique_bounds) / sample_size)

    # DSU performs well when q ranges repeat heavily (same bounds) because
    # cached bisect bounds and early full-assignment exits avoid heap churn.
    if duplicate_ratio >= 0.25:
        return "dsu"

    log_n = math.log2(tx_count + 1)
    log_q = math.log2(q_count + 1)
    heap_estimate = (2.0 * q_count + tx_count) * log_q
    dsu_estimate = q_count * log_n + tx_count

    # Keep heap unless DSU appears materially better.
    return "dsu" if dsu_estimate * 0.85 < heap_estimate else "heap"


def _q_overrides_heap(ordered_times: list[int], q_periods: list[dict]) -> list[float | None]:
    if not ordered_times or not q_periods:
        return [None] * len(ordered_times)

    q_sorted = sorted(q_periods, key=lambda q: (q["start_epoch"], q["index"]))
    q_pointer = 0
    active_q: list[tuple[int, int, int, float]] = []
    overrides: list[float | None] = [None] * len(ordered_times)

    for position, ts in enumerate(ordered_times):
        while q_pointer < len(q_sorted) and q_sorted[q_pointer]["start_epoch"] <= ts:
            q_period = q_sorted[q_pointer]
            heapq.heappush(
                active_q,
                (
                    -q_period["start_epoch"],
                    q_period["index"],
                    q_period["end_epoch"],
                    q_period["value"],
                ),
            )
            q_pointer += 1

        while active_q and active_q[0][2] < ts:
            heapq.heappop(active_q)

        if active_q:
            overrides[position] = active_q[0][3]
    return overrides


def _q_overrides_dsu(ordered_times: list[int], q_periods: list[dict]) -> list[float | None]:
    size = len(ordered_times)
    if size == 0 or not q_periods:
        return [None] * size

    q_priority_sorted = sorted(
        q_periods,
        key=lambda q: (-q["start_epoch"], q["index"]),
    )
    parent = list(range(size + 1))
    overrides: list[float | None] = [None] * size
    bounds_cache: dict[tuple[int, int], tuple[int, int]] = {}
    assigned_count = 0

    def find(next_index: int) -> int:
        while parent[next_index] != next_index:
            parent[next_index] = parent[parent[next_index]]
            next_index = parent[next_index]
        return next_index

    for q_period in q_priority_sorted:
        if assigned_count >= size:
            break

        cache_key = (q_period["start_epoch"], q_period["end_epoch"])
        bounds = bounds_cache.get(cache_key)
        if bounds is None:
            left = bisect_left(ordered_times, q_period["start_epoch"])
            right = bisect_right(ordered_times, q_period["end_epoch"]) - 1
            bounds_cache[cache_key] = (left, right)
        else:
            left, right = bounds
        if left > right:
            continue

        position = find(left)
        while position <= right:
            overrides[position] = q_period["value"]
            assigned_count += 1
            parent[position] = find(position + 1)
            position = parent[position]
    return overrides


def _merge_k_periods(k_periods: list[dict]) -> list[tuple[int, int]]:
    if not k_periods:
        return []

    sorted_periods = sorted(
        ((period["start_epoch"], period["end_epoch"]) for period in k_periods),
        key=lambda interval: (interval[0], interval[1]),
    )
    merged: list[tuple[int, int]] = []
    current_start, current_end = sorted_periods[0]

    for start, end in sorted_periods[1:]:
        if start <= current_end + 1:
            if end > current_end:
                current_end = end
            continue
        merged.append((current_start, current_end))
        current_start, current_end = start, end

    merged.append((current_start, current_end))
    return merged


def _membership_in_k(
    transactions: list[dict],
    k_periods: list[dict],
    *,
    ordered_indices: list[int] | None = None,
) -> list[bool]:
    if not transactions:
        return []
    if not k_periods:
        return [True] * len(transactions)

    if ordered_indices is None:
        ordered_indices = sorted(
            range(len(transactions)), key=lambda i: (transactions[i]["epoch"], i)
        )

    merged_k = _merge_k_periods(k_periods)
    if not merged_k:
        return [False] * len(transactions)

    memberships = [False] * len(transactions)
    interval_pointer = 0

    for tx_index in ordered_indices:
        ts = transactions[tx_index]["epoch"]
        while interval_pointer < len(merged_k) and merged_k[interval_pointer][1] < ts:
            interval_pointer += 1
        if interval_pointer < len(merged_k):
            start, end = merged_k[interval_pointer]
            memberships[tx_index] = start <= ts <= end

    return memberships


def filter_transactions(
    transactions: list[dict], q_periods: list[dict], p_periods: list[dict], k_periods: list[dict]
) -> dict:
    canonical_transactions: list[dict] = []
    invalid: list[dict] = []
    seen_timestamps: set[str] = set()

    for raw in transactions:
        try:
            tx = _canonical_transaction(
                raw, enforce_amount_limit=True, require_ceiling_and_remanent=False
            )
        except ValueError as exc:
            message = str(exc)
            if "Amount cannot be negative" in message:
                message = "Negative amounts are not allowed"
            invalid.append(_filter_invalid_output(raw, message))
            continue

        if tx["date"] in seen_timestamps:
            invalid.append(_filter_invalid_output(tx, "Duplicate transaction"))
            continue
        seen_timestamps.add(tx["date"])
        canonical_transactions.append(tx)

    ordered_indices = sorted(
        range(len(canonical_transactions)),
        key=lambda i: (canonical_transactions[i]["epoch"], i),
    )
    adjusted = _apply_temporal_rules(
        canonical_transactions,
        q_periods,
        p_periods,
        ordered_indices=ordered_indices,
    )
    membership = _membership_in_k(adjusted, k_periods, ordered_indices=ordered_indices)

    valid: list[dict] = []
    for tx, in_k in zip(adjusted, membership):
        adjusted_remanent = money(tx.get("adjusted_remanent", tx["remanent"]))
        if not in_k:
            invalid.append(
                _filter_invalid_output(tx, "Transaction is outside all k evaluation ranges.")
            )
            continue
        if adjusted_remanent <= 0:
            continue
        valid.append(
            {
                "date": tx["date"],
                "amount": money(tx["amount"]),
                "ceiling": money(tx["ceiling"]),
                "remanent": adjusted_remanent,
                "inKPeriod": True,
            }
        )

    return {"valid": valid, "invalid": invalid}


def aggregate_savings_by_k(
    transactions: list[dict], k_periods: list[dict], *, is_sorted: bool = False
) -> list[dict]:
    if not k_periods:
        return []

    ordered_transactions = transactions if is_sorted else sorted(transactions, key=lambda tx: tx["epoch"])
    times = [tx["epoch"] for tx in ordered_transactions]

    prefix = [0.0]
    for tx in ordered_transactions:
        value = tx.get("adjusted_remanent", tx["remanent"])
        prefix.append(prefix[-1] + value)

    savings: list[dict] = []
    for period in k_periods:
        left = bisect_left(times, period["start_epoch"])
        right = bisect_right(times, period["end_epoch"])
        savings.append(
            {
                "start": period["start"],
                "end": period["end"],
                "amount": money(prefix[right] - prefix[left]),
            }
        )
    return savings


def build_period_payload(q: list[dict], p: list[dict], k: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    q_periods = _build_periods(q, "q")
    p_periods = _build_periods(p, "p")
    k_periods = _build_periods(k, "k")
    return q_periods, p_periods, k_periods


def calculate_returns(
    *,
    instrument: str,
    age: int,
    wage: float,
    inflation: float,
    transactions: list[dict],
    q_periods: list[dict],
    p_periods: list[dict],
    k_periods: list[dict],
) -> dict:
    if age < 0:
        raise ValueError("Age cannot be negative.")
    if wage < 0:
        raise ValueError("Wage cannot be negative.")
    normalized_inflation = _normalize_inflation_rate(inflation)

    canonical_transactions, invalid_count, duplicate_count = _prepare_returns_transactions(transactions)
    if invalid_count or duplicate_count:
        logger.warning(
            "returns input filtered: invalid=%s duplicate=%s valid=%s",
            invalid_count,
            duplicate_count,
            len(canonical_transactions),
        )
    if not canonical_transactions:
        raise ValueError("No valid transactions available for returns calculation.")
    ordered_indices = sorted(
        range(len(canonical_transactions)),
        key=lambda i: (canonical_transactions[i]["epoch"], i),
    )
    adjusted_transactions = _apply_temporal_rules(
        canonical_transactions,
        q_periods,
        p_periods,
        ordered_indices=ordered_indices,
    )
    ordered_adjusted_transactions = [adjusted_transactions[index] for index in ordered_indices]
    savings = aggregate_savings_by_k(
        ordered_adjusted_transactions,
        k_periods,
        is_sorted=True,
    )

    years = years_to_investment_horizon(age)
    rate = NPS_RATE if instrument == "nps" else INDEX_RATE
    savings_by_dates: list[dict] = []

    for period_saving in savings:
        nominal_return, real_return, profit = compute_real_return(
            invested_amount=period_saving["amount"],
            annual_rate=rate,
            inflation_rate=normalized_inflation,
            years=years,
        )
        tax_benefit = nps_tax_benefit(period_saving["amount"], wage) if instrument == "nps" else 0.0
        savings_by_dates.append(
            {
                "start": period_saving["start"],
                "end": period_saving["end"],
                "amount": period_saving["amount"],
                "profits": profit,
                "taxBenefit": money(tax_benefit),
            }
        )

    return {
        "transactionsTotalAmount": money(sum(tx["amount"] for tx in canonical_transactions)),
        "transactionsTotalCeiling": money(sum(tx["ceiling"] for tx in canonical_transactions)),
        "savingsByDates": savings_by_dates,
    }
