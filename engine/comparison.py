"""
מנוע ההשוואה: מחבר usage_value + rules + net_calculator להשוואת "מצב היום"
מול חלופה (רכב אחר, רכב חשמלי, מסלול ברוכת ילדים, ויתור), ומחזיר טבלת
השוואה + הסבר במילים פשוטות. אין כאן קריאות ל-LLM בכלל - קוד טהור.

הערת היקף: עלות הרכב במסלול ברוכת ילדים (לצורך חישוב פער התקציב) ושיטת
הצירוף המדויקת של "חלק העובד בפער" להשתתפות החודשית הרגילה - עדיין לא
הוגדרו במפורש משטראוס (ראו config/rules.yaml: kids_track.dummy). ההנחה
שמומשה כאן: חלק העובד בפער (kids_track_gap_split.employee_share) מתווסף
להשתתפות העובד הרגילה (employee_participation), ומוצג כהערת-הסבר נפרדת.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine import rules as rules_engine
from engine.net_calculator import (
    NetCalculationResult,
    SalaryInputs,
    VehicleBenefitInputs,
    calculate_net,
    load_tax_tables,
)
from engine.usage_value import UsageValueRecord, find_usage_value


@dataclass
class VehicleScenario:
    label: str
    usage_value: float = 0.0
    employee_participation: float = 0.0
    electric_vehicle_bonus: float = 0.0
    car_waiver_allowance: float = 0.0
    notes: list[str] = field(default_factory=list)


@dataclass
class ComparisonResult:
    current_label: str
    alternative_label: str
    current: NetCalculationResult
    alternative: NetCalculationResult
    net_diff: float
    explanation_lines: list[str]


def scenario_from_vehicle(
    label: str,
    manufacturer_code: str,
    model_code: str,
    registration_year: int,
    vehicle_type_code: str | None = None,
    employee_participation: float = 0.0,
    is_electric: bool = False,
    rules: dict | None = None,
) -> tuple[VehicleScenario, UsageValueRecord]:
    """בונה תרחיש רכב (קיים/חדש/חשמלי) משליפת שווי שימוש אמיתית מהמאגר."""
    record = find_usage_value(
        manufacturer_code=manufacturer_code,
        model_code=model_code,
        registration_year=registration_year,
        vehicle_type_code=vehicle_type_code,
    )
    bonus = rules_engine.electric_vehicle_bonus(rules) if is_electric else 0.0
    notes = [f"שווי שימוש חודשי: {record.usage_value:.0f} ₪ ({record.manufacturer_name} {record.trade_name})"]
    if is_electric:
        notes.append(f"תוספת רכב חשמלי: +{bonus:.0f} ₪ נטו (החזר חשמל)")
    if employee_participation:
        notes.append(f"השתתפות העובד/ת: {employee_participation:.0f} ₪")
    scenario = VehicleScenario(
        label=label,
        usage_value=record.usage_value,
        employee_participation=employee_participation,
        electric_vehicle_bonus=bonus,
        notes=notes,
    )
    return scenario, record


def scenario_from_waiver(label: str, occupation: str, rules: dict | None = None) -> VehicleScenario:
    allowance = rules_engine.waiver_allowance(occupation, rules)
    return VehicleScenario(
        label=label,
        car_waiver_allowance=allowance,
        notes=[f"ויתור על רכב: אחזקת רכב {allowance:.0f} ₪ (עיסוק: {occupation})"],
    )


def scenario_from_kids_track(
    label: str,
    manufacturer_code: str,
    model_code: str,
    registration_year: int,
    employee_group: str,
    car_cost: float,
    vehicle_type_code: str | None = None,
    base_employee_participation: float = 0.0,
    is_electric: bool = False,
    rules: dict | None = None,
) -> tuple[VehicleScenario, UsageValueRecord]:
    record = find_usage_value(
        manufacturer_code=manufacturer_code,
        model_code=model_code,
        registration_year=registration_year,
        vehicle_type_code=vehicle_type_code,
    )
    budget = rules_engine.budget_for_group(employee_group, rules)
    split = rules_engine.kids_track_gap_split(budget, car_cost, rules)
    bonus = rules_engine.electric_vehicle_bonus(rules) if is_electric else 0.0
    total_participation = base_employee_participation + split.employee_share

    notes = [f"שווי שימוש חודשי: {record.usage_value:.0f} ₪ ({record.manufacturer_name} {record.trade_name})"]
    if split.gap > 0:
        notes.append(
            f"מסלול ברוכת ילדים: עלות {split.car_cost:.0f} ₪ מעל תקציב {split.budget:.0f} ₪ "
            f"(פער {split.gap:.0f} ₪) -> מעסיק {split.employer_share:.0f} ₪ / עובד/ת {split.employee_share:.0f} ₪"
        )
    if is_electric:
        notes.append(f"תוספת רכב חשמלי: +{bonus:.0f} ₪ נטו (החזר חשמל)")

    scenario = VehicleScenario(
        label=label,
        usage_value=record.usage_value,
        employee_participation=total_participation,
        electric_vehicle_bonus=bonus,
        notes=notes,
    )
    return scenario, record


def compare(
    salary: SalaryInputs,
    current: VehicleScenario,
    alternative: VehicleScenario,
    tax_tables: dict | None = None,
) -> ComparisonResult:
    tax_tables = tax_tables or load_tax_tables()

    current_result = calculate_net(
        salary,
        VehicleBenefitInputs(
            usage_value=current.usage_value,
            employee_participation=current.employee_participation,
            electric_vehicle_net_bonus=current.electric_vehicle_bonus,
            car_waiver_allowance=current.car_waiver_allowance,
        ),
        tax_tables,
    )
    alternative_result = calculate_net(
        salary,
        VehicleBenefitInputs(
            usage_value=alternative.usage_value,
            employee_participation=alternative.employee_participation,
            electric_vehicle_net_bonus=alternative.electric_vehicle_bonus,
            car_waiver_allowance=alternative.car_waiver_allowance,
        ),
        tax_tables,
    )

    net_diff = round(alternative_result.net_pay - current_result.net_pay, 2)

    explanation_lines = [
        f"{current.label}: נטו {current_result.net_pay:,.0f} ₪ · {alternative.label}: נטו {alternative_result.net_pay:,.0f} ₪ "
        f"· הפרש {'+' if net_diff >= 0 else ''}{net_diff:,.0f} ₪ בחודש.",
    ]
    explanation_lines.extend(alternative.notes)

    return ComparisonResult(
        current_label=current.label,
        alternative_label=alternative.label,
        current=current_result,
        alternative=alternative_result,
        net_diff=net_diff,
        explanation_lines=explanation_lines,
    )
