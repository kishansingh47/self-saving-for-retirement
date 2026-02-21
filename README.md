# Self Saving for Retirement - BlackRock Challenge

Production-style API implementation for the retirement auto-saving challenge.

## Tech Stack
- Python 3.12
- FastAPI
- Pydantic
- Pytest

## Project Structure
- `app/main.py`: API entrypoint and route handlers
- `app/core/engine.py`: Core business logic (parse, validate, q/p/k, returns)
- `app/core/finance.py`: Rounding, tax, and return formulas
- `app/core/time_utils.py`: Timestamp parsing and normalization
- `app/models/schemas.py`: Request/response contracts
- `test/`: Unit and API tests

## Run Locally
```bash
python -m venv .venv
. .venv/Scripts/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 5477 --reload
```

Swagger UI:
- `http://localhost:5477/docs`

## Required Endpoints
- `POST /blackrock/challenge/v1/transactions:parse`
- `POST /blackrock/challenge/v1/transactions:validator`
- `POST /blackrock/challenge/v1/transactions:filter`
- `POST /blackrock/challenge/v1/returns:nps`
- `POST /blackrock/challenge/v1/returns:index`
- `GET /blackrock/challenge/v1/performance`

## Business Rule Coverage
- Parse expenses into transactions (`ceiling`, `remanent`)
- Validate transactions, duplicates, and investment limit checks
- Apply temporal rules:
  - `q`: fixed amount override with latest-start precedence
  - `p`: additive extras (all matching periods)
  - `k`: inclusive interval aggregation via prefix sums
- Compute NPS and Index returns:
  - Compound annual growth
  - Inflation-adjusted real returns
  - NPS tax benefit using provided simplified slabs

## Solution Document
This section explains the implementation strategy, boundary handling, and runtime behavior used in this solution.

## Implementation Approach
- API Layer:
  - Implemented with FastAPI route handlers in `app/main.py`.
  - Endpoints are thin wrappers; core logic is delegated to `app/core/engine.py`.
- Domain/Computation Layer:
  - `engine.py` handles parsing, validation, temporal rule application (`q/p/k`), and returns generation.
  - `finance.py` centralizes formulas for rounding, tax slabs, deduction cap, and return calculations.
  - `time_utils.py` performs strict timestamp parsing and normalization to `YYYY-MM-DD HH:mm:ss`.
- Contract Layer:
  - Pydantic models in `app/models/schemas.py` define request/response schemas.
  - Manual compatibility support is included for challenge-style list payloads where required.

## Temporal Logic and Complexity
- Processing order follows challenge rules:
  - Base remanent calculation
  - `q` override
  - `p` additive extras
  - `k` grouping/evaluation
  - returns calculation
- `q` handling:
  - Hybrid strategy in `engine.py` chooses between heap-based and DSU-based override computation.
  - Selection is data-aware to improve behavior under different overlap/distribution patterns.
- `p` handling:
  - Start/end event sweep line computes additive extras efficiently in sorted timestamp order.
- `k` handling:
  - Merged intervals + ordered scan for membership checks.
  - Prefix-sum + binary search (`bisect`) for amount aggregation in returns path.
- Complexity (practical):
  - Dominated by sorting and event sweeps; designed for large inputs (up to challenge scale).
  - Aggregation by `k` is efficient (`O(k log n)` for prefix/bisect path).

## Boundary Conditions and Validation
Validation is enforced in two layers:
- FastAPI/Pydantic request parsing (`422` on malformed JSON or schema/type mismatch)
- Engine business-rule checks (`400` with explicit validation message)

| Area | Validation Rule | Failure Behavior | Implemented In |
|---|---|---|---|
| JSON and schema | Invalid JSON, missing required top-level fields, wrong structural types | `422 Unprocessable Content` | FastAPI + Pydantic models in `app/models/schemas.py` |
| Timestamp format | Must be `YYYY-MM-DD HH:mm:ss` (or `YYYY-MM-DD HH:mm`, normalized to seconds) | `400` with format error | `app/core/time_utils.py` |
| Transaction timestamp presence | Each transaction/expense must have `date` or `timestamp` | `400` | `_canonical_transaction`, `build_transactions` in `app/core/engine.py` |
| Transaction numeric parsing | Numeric fields (`amount`, `ceiling`, `remanent`, `fixed`, `extra`) must be numeric | `400` | `_to_float` in `app/core/engine.py` |
| Amount bounds | `amount >= 0` and `amount < 500000` (strict challenge bound) | `400` | `_canonical_transaction`, `build_transactions` in `app/core/engine.py` |
| Ceiling/remanent consistency (validator) | `ceiling >= amount`, `remanent >= 0`, and exact checks: `ceiling == nextMultipleOf100(amount)`, `remanent == ceiling - amount` | Transaction moved to `invalid[]` with message | `validate_transactions` in `app/core/engine.py` |
| Duplicate detection | Duplicate transaction timestamp (`date`/`timestamp`) | `transactions:validator`: moved to `duplicates[]`; `transactions:filter`: moved to `invalid[]`; returns endpoints: dropped from calculation with warning log | `validate_transactions`, `filter_transactions`, `_prepare_returns_transactions` in `app/core/engine.py` |
| Wage/limit checks | `wage >= 0`; `maxInvestment` (if provided) must be non-negative | `400` | `validate_transactions` in `app/core/engine.py` |
| Cumulative investment limit | Running sum of remanent cannot exceed max investment (default `wage * 12`) | Transaction moved to `invalid[]` | `validate_transactions` in `app/core/engine.py` |
| Period validity (`q/p/k`) | `start` and `end` required; `start <= end`; `k` cannot span multiple years | `400` | `_build_periods` in `app/core/engine.py` |
| Period bounds (`q/p`) | `q.fixed >= 0` and `< 500000`; `p.extra >= 0` and `< 500000` | `400` | `_build_periods` in `app/core/engine.py` |
| `q` precedence | If multiple `q` periods match: latest `start` wins; tie-breaker = earlier list index | Deterministic override selection | `_q_overrides_heap`, `_q_overrides_dsu` in `app/core/engine.py` |
| `k` membership in filter | Transactions outside all `k` ranges are invalid in `transactions:filter` | Transaction moved to `invalid[]` with message | `filter_transactions` in `app/core/engine.py` |
| Non-positive adjusted remanent | Transactions with adjusted remanent `<= 0` are excluded from `valid[]` in filter | Skipped from valid output | `filter_transactions` in `app/core/engine.py` |
| Returns input sanitation | Invalid/duplicate transactions are filtered and computation continues with valid subset | Warning logged; if no valid transactions remain, `400` | `_prepare_returns_transactions`, `calculate_returns` in `app/core/engine.py` |
| Returns scalar checks | `age >= 0`, `wage >= 0`, `inflation >= 0` | `400` | `calculate_returns`, `_normalize_inflation_rate` in `app/core/engine.py` |
| Inflation interpretation | `inflation > 1` is interpreted as percent (`5.5 -> 0.055`), else decimal | Normalized before return math | `_normalize_inflation_rate` in `app/core/engine.py` |
| NPS tax benefit cap | Deduction is `min(invested, 10% annual income, 200000)` | Applied in output computation | `nps_tax_benefit` in `app/core/finance.py` |

## Endpoint Notes
- `transactions:parse`
  - Returns list of transactions with `date`, `amount`, `ceiling`, `remanent`.
- `transactions:validator`
  - Returns `valid`, `invalid`, and `duplicates` buckets.
- `transactions:filter`
  - Accepts sparse transaction input (`date/timestamp + amount`), computes missing fields, applies `q/p/k`.
- `returns:nps` and `returns:index`
  - Output shape:
    - `transactionsTotalAmount`
    - `transactionsTotalCeiling`
    - `savingsByDates[]` with `start`, `end`, `amount`, `profits`, `taxBenefit`.
  - `taxBenefit` is `0` for index endpoint.

## Test Execution
```bash
pytest -q
```

Tests are inside `test/` and include comments required by the challenge:
- Test type
- Validation purpose
- Execution command

## Docker
Build image:
```bash
docker build -t blk-hacking-ind-name-lastname .
```

Run container:
```bash
docker run -d -p 5477:5477 blk-hacking-ind-name-lastname
```
