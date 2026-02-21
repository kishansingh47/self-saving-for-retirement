from __future__ import annotations

from pydantic import BaseModel, Field


class ExpenseInput(BaseModel):
    date: str | None = None
    timestamp: str | None = None
    amount: float


class TransactionInput(BaseModel):
    date: str | None = None
    timestamp: str | None = None
    amount: float
    ceiling: float
    remanent: float


class TransactionOutput(BaseModel):
    date: str
    amount: float
    ceiling: float
    remanent: float
    adjustedRemanent: float | None = None


class InvalidTransactionOutput(TransactionOutput):
    message: str


class ParseRequest(BaseModel):
    expenses: list[ExpenseInput] = Field(default_factory=list)


class ParseTransactionOutput(BaseModel):
    date: str
    amount: float
    ceiling: float
    remanent: float


class ValidatorRequest(BaseModel):
    wage: float
    maxInvestment: float | None = None
    transactions: list[TransactionInput] = Field(default_factory=list)


class ValidatorTransactionOutput(BaseModel):
    date: str
    amount: float
    ceiling: float
    remanent: float


class InvalidValidatorTransactionOutput(ValidatorTransactionOutput):
    message: str


class ValidatorResponse(BaseModel):
    valid: list[ValidatorTransactionOutput]
    invalid: list[InvalidValidatorTransactionOutput]
    duplicates: list[InvalidValidatorTransactionOutput]


class QPeriodInput(BaseModel):
    fixed: float
    start: str
    end: str


class PPeriodInput(BaseModel):
    extra: float
    start: str
    end: str


class KPeriodInput(BaseModel):
    start: str
    end: str


class FilterTransactionInput(BaseModel):
    date: str | None = None
    timestamp: str | None = None
    amount: float
    ceiling: float | None = None
    remanent: float | None = None


class FilterRequest(BaseModel):
    q: list[QPeriodInput] = Field(default_factory=list)
    p: list[PPeriodInput] = Field(default_factory=list)
    k: list[KPeriodInput] = Field(default_factory=list)
    transactions: list[FilterTransactionInput] = Field(default_factory=list)


class FilterValidTransactionOutput(BaseModel):
    date: str
    amount: float
    ceiling: float
    remanent: float
    inKPeriod: bool


class FilterInvalidTransactionOutput(BaseModel):
    date: str
    amount: float
    message: str


class FilterResponse(BaseModel):
    valid: list[FilterValidTransactionOutput]
    invalid: list[FilterInvalidTransactionOutput]


class ReturnsRequest(BaseModel):
    age: int
    wage: float
    inflation: float
    q: list[QPeriodInput] = Field(default_factory=list)
    p: list[PPeriodInput] = Field(default_factory=list)
    k: list[KPeriodInput] = Field(default_factory=list)
    transactions: list[FilterTransactionInput] = Field(default_factory=list)


class SavingsByDateOutput(BaseModel):
    start: str
    end: str
    amount: float
    profits: float
    taxBenefit: float


class ReturnsResponse(BaseModel):
    transactionsTotalAmount: float
    transactionsTotalCeiling: float
    savingsByDates: list[SavingsByDateOutput]


class PerformanceResponse(BaseModel):
    time: str
    memory: str
    threads: int
