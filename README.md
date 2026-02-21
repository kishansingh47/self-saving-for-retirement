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
