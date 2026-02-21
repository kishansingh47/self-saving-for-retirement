from __future__ import annotations

from decimal import Decimal, ROUND_CEILING


HUNDRED = Decimal("100")
TWELVE = Decimal("12")
NPS_RATE = Decimal("0.0711")
INDEX_RATE = Decimal("0.1449")
NPS_ABSOLUTE_DEDUCTION_CAP = Decimal("200000")
TAX_SLAB_1_MAX = Decimal("700000")
TAX_SLAB_2_MAX = Decimal("1000000")
TAX_SLAB_3_MAX = Decimal("1200000")
TAX_SLAB_4_MAX = Decimal("1500000")
TAX_RATE_10 = Decimal("0.10")
TAX_RATE_15 = Decimal("0.15")
TAX_RATE_20 = Decimal("0.20")
TAX_RATE_30 = Decimal("0.30")


def to_decimal(value: float | int | str) -> Decimal:
    return Decimal(str(value))


def money(value: float | Decimal, digits: int = 2) -> float:
    return round(float(value), digits)


def next_multiple_of_100(amount: float) -> float:
    value = to_decimal(amount)
    if value < 0:
        raise ValueError("Amount cannot be negative.")
    multiplier = (value / HUNDRED).to_integral_value(rounding=ROUND_CEILING)
    return money(multiplier * HUNDRED)


def remanent_from_amount(amount: float) -> float:
    ceiling = next_multiple_of_100(amount)
    return money(to_decimal(ceiling) - to_decimal(amount))


def compute_tax(income: float) -> float:
    annual_income = to_decimal(max(0, income))
    if annual_income <= TAX_SLAB_1_MAX:
        return 0.0
    if annual_income <= TAX_SLAB_2_MAX:
        return money((annual_income - TAX_SLAB_1_MAX) * TAX_RATE_10)
    if annual_income <= TAX_SLAB_3_MAX:
        return money(
            Decimal("30000") + (annual_income - TAX_SLAB_2_MAX) * TAX_RATE_15
        )
    if annual_income <= TAX_SLAB_4_MAX:
        return money(
            Decimal("60000") + (annual_income - TAX_SLAB_3_MAX) * TAX_RATE_20
        )
    return money(
        Decimal("120000") + (annual_income - TAX_SLAB_4_MAX) * TAX_RATE_30
    )


def nps_tax_benefit(invested_amount: float, monthly_wage: float) -> float:
    annual_income = to_decimal(monthly_wage) * TWELVE
    deduction = min(
        to_decimal(invested_amount),
        annual_income * TAX_RATE_10,
        NPS_ABSOLUTE_DEDUCTION_CAP,
    )
    tax_before = compute_tax(float(annual_income))
    tax_after = compute_tax(float(annual_income - deduction))
    return money(tax_before - tax_after)


def years_to_investment_horizon(age: int) -> int:
    return 60 - age if age < 60 else 5


def compute_real_return(
    invested_amount: float, annual_rate: Decimal, inflation_rate: float, years: int
) -> tuple[float, float, float]:
    principal = to_decimal(invested_amount)
    if principal < 0:
        raise ValueError("Invested amount cannot be negative.")
    if inflation_rate < 0:
        raise ValueError("Inflation rate cannot be negative.")
    if years <= 0:
        raise ValueError("Years must be greater than zero.")

    inflation = to_decimal(inflation_rate)
    nominal_return = principal * ((Decimal("1") + annual_rate) ** years)
    real_return = nominal_return / ((Decimal("1") + inflation) ** years)
    profit = real_return - principal
    return money(nominal_return), money(real_return), money(profit)
