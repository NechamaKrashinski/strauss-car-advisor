"""
מנוע חישוב נטו טהור — ללא תלות ב-LLM. ראו config/tax_tables.yaml למקורות
ולהסתייגות לגבי דיוק המספרים (קירוב ממקורות משניים, לא פרסום רשמי).

מודל מפושט אך מבוסס-היגיון של שכר ישראלי:
- "שווי שימוש" של רכב הוא תוספת חייבת מס + ביטוח לאומי, אך לא מזומן בפועל.
- השתתפות העובד בעלות הרכב (employee_participation) מקטינה גם את שווי
  השימוש החייב במס *וגם* מנוכה כמזומן בפועל מהנטו (כך משלמים עליה פעם
  אחת, לא פעמיים).
- תוספת רכב חשמלי (electric_vehicle_net_bonus) מוגדרת ב-rules.yaml כ"נטו"
  (grossed_up: false) — מתווספת ישירות לנטו הסופי, לא עוברת דרך מנוע המס.
- "אחזקת רכב" בוויתור (car_waiver_allowance) היא מזומן חייב מס, אך לא נכנסת
  לבסיס פנסיה/קרן השתלמות (תואם rules.yaml: "לא כולל רכיבים סוציאליים").
- פנסיה/קרן השתלמות מחושבות על בסיס שכר+רכיבים בלבד (לא על תוספות רכב),
  ומנוכות גם מההכנסה החייבת במס (בגבולות הפטור המקובלים).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

DEFAULT_TAX_TABLES_PATH = Path(__file__).resolve().parent.parent / "config" / "tax_tables.yaml"


@lru_cache(maxsize=1)
def load_tax_tables(path: str = str(DEFAULT_TAX_TABLES_PATH)) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass(frozen=True)
class SalaryInputs:
    base_salary: float
    variable_components: float = 0.0
    pension_employee_rate: float = 0.0
    keren_hishtalmut_employee_rate: float = 0.0
    credit_points: float = 2.25


@dataclass(frozen=True)
class VehicleBenefitInputs:
    usage_value: float = 0.0
    employee_participation: float = 0.0
    electric_vehicle_net_bonus: float = 0.0
    car_waiver_allowance: float = 0.0


@dataclass(frozen=True)
class NetCalculationResult:
    cash_components: float
    non_cash_taxable_addition: float
    gross_taxable_income: float
    pension_deduction: float
    keren_hishtalmut_deduction: float
    taxable_income_for_tax: float
    income_tax_gross: float
    credit_amount: float
    income_tax_after_credit: float
    national_insurance_total: float
    net_pay: float


def _income_tax_gross(taxable_income: float, tax_tables: dict) -> float:
    """מס מדורג על ההכנסה החייבת (מדרגות חודשיות)."""
    brackets = tax_tables["income_tax_brackets_monthly"]
    tax = 0.0
    lower = 0.0
    for bracket in brackets:
        upper = bracket["upper_bound"]
        rate = bracket["rate"]
        if upper is None or taxable_income <= upper:
            tax += max(0.0, taxable_income - lower) * rate
            return tax
        tax += (upper - lower) * rate
        lower = upper
    return tax


def _national_insurance(gross: float, tax_tables: dict) -> float:
    cfg = tax_tables["national_insurance_employee"]
    ceiling = cfg["income_ceiling_monthly"]
    reduced_ceiling = cfg["reduced_bracket_ceiling_monthly"]
    capped_gross = min(gross, ceiling)

    reduced_part = min(capped_gross, reduced_ceiling)
    full_part = max(0.0, capped_gross - reduced_ceiling)

    reduced_total = reduced_part * (cfg["reduced_rate_bituach_leumi"] + cfg["reduced_rate_health"])
    full_total = full_part * (cfg["full_rate_bituach_leumi"] + cfg["full_rate_health"])
    return reduced_total + full_total


def calculate_net(
    salary: SalaryInputs,
    vehicle: VehicleBenefitInputs | None = None,
    tax_tables: dict | None = None,
) -> NetCalculationResult:
    vehicle = vehicle or VehicleBenefitInputs()
    tax_tables = tax_tables or load_tax_tables()

    cash_components = salary.base_salary + salary.variable_components + vehicle.car_waiver_allowance
    non_cash_taxable_addition = max(0.0, vehicle.usage_value - vehicle.employee_participation)
    gross_taxable_income = cash_components + non_cash_taxable_addition

    pension_base = salary.base_salary + salary.variable_components
    pension_deduction = pension_base * salary.pension_employee_rate
    keren_deduction = pension_base * salary.keren_hishtalmut_employee_rate

    taxable_income_for_tax = max(0.0, gross_taxable_income - pension_deduction - keren_deduction)
    income_tax_gross = _income_tax_gross(taxable_income_for_tax, tax_tables)

    credit_amount = salary.credit_points * tax_tables["credit_point_value_monthly"]
    income_tax_after_credit = max(0.0, income_tax_gross - credit_amount)

    national_insurance_total = _national_insurance(gross_taxable_income, tax_tables)

    net_pay = (
        cash_components
        - pension_deduction
        - keren_deduction
        - vehicle.employee_participation
        - income_tax_after_credit
        - national_insurance_total
        + vehicle.electric_vehicle_net_bonus
    )

    return NetCalculationResult(
        cash_components=cash_components,
        non_cash_taxable_addition=non_cash_taxable_addition,
        gross_taxable_income=gross_taxable_income,
        pension_deduction=pension_deduction,
        keren_hishtalmut_deduction=keren_deduction,
        taxable_income_for_tax=taxable_income_for_tax,
        income_tax_gross=income_tax_gross,
        credit_amount=credit_amount,
        income_tax_after_credit=income_tax_after_credit,
        national_insurance_total=national_insurance_total,
        net_pay=round(net_pay, 2),
    )
