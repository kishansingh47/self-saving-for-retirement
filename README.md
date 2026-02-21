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
- Timestamp rules:
  - Accepted format: `YYYY-MM-DD HH:mm:ss` (also supports `YYYY-MM-DD HH:mm` and normalizes seconds).
  - Period ranges are inclusive.
  - `k` ranges cannot span multiple years.
- Transaction amount rules:
  - Negative amounts are invalid.
  - `amount` must be `< 500000` when constraint enforcement is enabled.
  - Duplicates are detected by timestamp (`date`/`timestamp`) as per challenge uniqueness rule.
- `q`/`p` bounds:
  - `q.fixed` must be non-negative and `< 500000`.
  - `p.extra` must be non-negative and `< 500000`.
- `q` precedence:
  - If multiple `q` ranges match, latest start date wins.
  - If starts are the same, first period in list wins.
- Returns behavior:
  - Returns endpoints compute using the valid subset of transactions.
  - Invalid/duplicate transactions are filtered internally (with warning logs).
  - If no valid transactions remain, the endpoint returns `400`.
- Inflation interpretation:
  - `inflation > 1` is treated as percent (`5.5` -> `0.055`).
  - `inflation <= 1` is treated as decimal rate.
- NPS tax benefit:
  - Deduction uses `min(invested_amount, 10% of annual income, 200000)`.
  - Tax slab logic follows challenge simplification in `finance.py`.

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
