from __future__ import annotations

import os
import threading
import time

import psutil
from fastapi import FastAPI, HTTPException, Request

from app.core.engine import (
    build_period_payload,
    build_transactions,
    calculate_returns,
    filter_transactions,
    validate_transactions,
)
from app.models.schemas import (
    ExpenseInput,
    FilterRequest,
    FilterResponse,
    ParseTransactionOutput,
    ParseRequest,
    PerformanceResponse,
    ReturnsRequest,
    ReturnsResponse,
    ValidatorRequest,
    ValidatorResponse,
)

app = FastAPI(
    title="Self Saving for Retirement Challenge API",
    version="1.0.0",
)

app.state.last_request_ms = 0.0


@app.middleware("http")
async def collect_request_metrics(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    app.state.last_request_ms = elapsed_ms
    return response


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post(
    "/blackrock/challenge/v1/transactions:parse",
    response_model=list[ParseTransactionOutput],
)
def parse_transactions(payload: ParseRequest | list[ExpenseInput]) -> list[ParseTransactionOutput]:
    if isinstance(payload, list):
        expenses = [expense.model_dump(exclude_none=True) for expense in payload]
    else:
        expenses = [expense.model_dump(exclude_none=True) for expense in payload.expenses]

    try:
        result = build_transactions(expenses)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [
        ParseTransactionOutput(
            date=tx["date"],
            amount=tx["amount"],
            ceiling=tx["ceiling"],
            remanent=tx["remanent"],
        )
        for tx in result["transactions"]
    ]


@app.post(
    "/blackrock/challenge/v1/transactions:validator",
    response_model=ValidatorResponse,
)
def validate_transactions_endpoint(payload: ValidatorRequest) -> ValidatorResponse:
    try:
        result = validate_transactions(
            wage=payload.wage,
            max_investment=payload.maxInvestment,
            transactions=[tx.model_dump() for tx in payload.transactions],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ValidatorResponse(**result)


@app.post(
    "/blackrock/challenge/v1/transactions:filter",
    response_model=FilterResponse,
)
def filter_transactions_endpoint(payload: FilterRequest) -> FilterResponse:
    try:
        q_periods, p_periods, k_periods = build_period_payload(
            [period.model_dump() for period in payload.q],
            [period.model_dump() for period in payload.p],
            [period.model_dump() for period in payload.k],
        )
        result = filter_transactions(
            transactions=[tx.model_dump() for tx in payload.transactions],
            q_periods=q_periods,
            p_periods=p_periods,
            k_periods=k_periods,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FilterResponse(**result)


def _returns_response(payload: ReturnsRequest, instrument: str) -> ReturnsResponse:
    try:
        q_periods, p_periods, k_periods = build_period_payload(
            [period.model_dump() for period in payload.q],
            [period.model_dump() for period in payload.p],
            [period.model_dump() for period in payload.k],
        )
        result = calculate_returns(
            instrument=instrument,
            age=payload.age,
            wage=payload.wage,
            inflation=payload.inflation,
            transactions=[tx.model_dump() for tx in payload.transactions],
            q_periods=q_periods,
            p_periods=p_periods,
            k_periods=k_periods,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ReturnsResponse(**result)


@app.post(
    "/blackrock/challenge/v1/returns:nps",
    response_model=ReturnsResponse,
)
def returns_nps(payload: ReturnsRequest) -> ReturnsResponse:
    return _returns_response(payload, instrument="nps")


@app.post(
    "/blackrock/challenge/v1/returns:index",
    response_model=ReturnsResponse,
)
def returns_index(payload: ReturnsRequest) -> ReturnsResponse:
    return _returns_response(payload, instrument="index")


@app.get(
    "/blackrock/challenge/v1/performance",
    response_model=PerformanceResponse,
)
def performance_report() -> PerformanceResponse:
    process = psutil.Process(os.getpid())
    memory_mb = process.memory_info().rss / (1024 * 1024)
    threads = threading.active_count()
    return PerformanceResponse(
        time=f"{app.state.last_request_ms:.3f} ms",
        memory=f"{memory_mb:.2f} MB",
        threads=threads,
    )
